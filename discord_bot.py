"""Optional Discord Gateway integration; shares the server's voting database."""
import asyncio
import hashlib
import json
import logging
import threading
from urllib.parse import urlsplit

import discord
from discord import app_commands

LOG = logging.getLogger('kr_discord')


def fingerprint(snapshot):
    keys = ('round_id','player','floor','active','items','votesCount','minimum_votes','url')
    return hashlib.sha256(json.dumps({k:snapshot[k] for k in keys},sort_keys=True).encode()).hexdigest()


def voting_embed(snapshot):
    embed = discord.Embed(title=f'Killing Room · Level {snapshot["floor"]}',
                          description=discord.utils.escape_markdown(snapshot['player'])[:1000],
                          colour=0xffbe42 if snapshot['active'] else 0x777777)
    for index,item in enumerate(snapshot['items']):
        label = discord.utils.escape_markdown(item['label'])[:200]
        embed.add_field(name=f'{index+1}. {label}', value=f'{item["votes"]} Stimme(n)', inline=False)
    status = 'Abstimmung offen' if snapshot['active'] else 'Abstimmung beendet'
    embed.set_footer(text=f'{status} · {snapshot["votesCount"]}/{snapshot["minimum_votes"]} Mindeststimmen')
    return embed


def stats_embed(stats):
    embed = discord.Embed(title='Killing Room · Statistik', colour=0x9cdebd,
        description=f'{stats["runs"]} Spielrunden · {stats["votes"]} Stimmen\n'
                    f'{stats["boss_wins"]} Boss-Siege · {stats["boss_deaths"]} Niederlagen')
    for boss in stats['bosses'][:20]:
        rate = f'{boss["win_percentage"]:g} %' if boss['win_percentage'] is not None else 'keine Daten'
        embed.add_field(name=f'Boss / Level {boss["boss"]}',
                        value=f'{rate} Siege · {boss["wins"]} gewonnen / {boss["deaths"]} verloren', inline=False)
    embed.set_footer(text='Quote unter erfassten Bossausgängen auf diesem Server.')
    return embed


class VoteButton(discord.ui.Button):
    def __init__(self, store, snapshot, item, index):
        super().__init__(label=f'{index+1}. {item["label"]}'[:80],
            style=discord.ButtonStyle.success if item['kind']=='good' else discord.ButtonStyle.danger,
            custom_id=f'kr:{snapshot["round_id"]}:{index}', disabled=not snapshot['active'], row=index//2)
        self.store, self.token, self.round_id, self.item_id = store,snapshot['token'],snapshot['round_id'],item['id']

    async def callback(self, interaction):
        # Discord supplies an authenticated account ID. Store a hash, not the raw ID.
        voter = 'discord:'+hashlib.sha256(str(interaction.user.id).encode()).hexdigest()
        try:
            self.store.vote(self.token, voter, self.round_id, self.item_id)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
        else:
            await interaction.response.send_message('Deine Stimme ist gespeichert. Ein weiterer Klick ändert deine Auswahl.',
                                                     ephemeral=True)


class VotingView(discord.ui.View):
    def __init__(self, store, snapshot):
        super().__init__(timeout=None)
        for index,item in enumerate(snapshot['items']):
            self.add_item(VoteButton(store,snapshot,item,index))
        if urlsplit(snapshot['url']).hostname not in ('127.0.0.1','localhost','::1'):
            self.add_item(discord.ui.Button(label='Im Browser öffnen', url=snapshot['url'],row=2))


class VotingBot(discord.Client):
    def __init__(self, store, channel_id, guild_id, registry=None):
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self.store, self.channel_id, self.guild_id = store, int(channel_id or 0), int(guild_id or 0)
        self.registry=registry
        self.tree = app_commands.CommandTree(self)
        self.publisher = None

        @self.tree.command(name='krstats', description='Erfasste Killing-Room-Bossstatistik anzeigen')
        async def krstats(interaction: discord.Interaction):
            await interaction.response.send_message(embed=stats_embed(store.statistics()), ephemeral=True)

        @self.tree.command(name='krlink', description='Aktuelle Killing-Room-Abstimmung anzeigen')
        async def krlink(interaction: discord.Interaction):
            live = [s for s in store.discord_snapshots() if s['active'] and
                    self.destination(s)==(interaction.channel_id,interaction.guild_id)]
            text = live[-1]['url'] if live else 'Gerade ist keine Abstimmung geöffnet.'
            await interaction.response.send_message(text, ephemeral=True)

    async def setup_hook(self):
        guilds={self.guild_id} if self.guild_id else set()
        if self.registry:
            guilds.update(int(r['discord_guild_id']) for r in self.registry.records() if str(r.get('discord_guild_id','')).isdigit())
        for guild_id in guilds:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
            except discord.HTTPException:
                LOG.warning('Slash-Kommandos konnten fuer einen Discord-Server nicht registriert werden.')
        for snap in self.store.discord_snapshots():
            if snap['message_id'] and snap['active']:
                self.add_view(VotingView(self.store,snap),message_id=int(snap['message_id']))
        self.publisher = asyncio.create_task(self.publish_loop())

    async def on_ready(self):
        LOG.info('Discord-Bot bereit; Abstimmungskanal konfiguriert.')

    def destination(self,snapshot):
        if snapshot['client_id']=='legacy':
            return self.channel_id,self.guild_id
        client=self.registry.get(snapshot['client_id']) if self.registry else None
        if client and str(client.get('discord_channel_id','')).isdigit() and str(client.get('discord_guild_id','')).isdigit():
            return int(client['discord_channel_id']),int(client['discord_guild_id'])
        return 0,0

    async def publish_one(self,snap):
        channel_id,guild_id=self.destination(snap)
        if not channel_id or not guild_id:return
        channel=self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if getattr(channel.guild,'id',None)!=guild_id:
            raise ValueError('Discord-Kanal und Server-ID passen nicht zusammen.')
        stamp = fingerprint(snap)
        if snap['message_id'] and snap['payload_hash']==stamp:
            return
        message = None
        if snap['message_id']:
            if str(snap['channel_id']) != str(channel_id):
                return
            try:
                message = await channel.fetch_message(int(snap['message_id']))
            except discord.NotFound:
                pass
        view = VotingView(self.store,snap)
        if message is not None:
            await message.edit(embed=voting_embed(snap),view=view,allowed_mentions=discord.AllowedMentions.none())
        elif snap['active']:
            message = await channel.send(embed=voting_embed(snap),view=view,
                allowed_mentions=discord.AllowedMentions.none(),silent=True,
                nonce=snap['round_id'])
        if message is not None:
            self.store.record_discord_message(snap['round_id'],channel_id,message.id,stamp,not snap['active'])
        elif snap['message_id'] and not snap['active']:
            self.store.record_discord_message(snap['round_id'],channel_id,snap['message_id'],stamp,True)

    async def publish_loop(self):
        await self.wait_until_ready()
        while not self.is_closed():
            for snap in self.store.discord_snapshots():
                try:
                    await self.publish_one(snap)
                except (discord.HTTPException,ValueError) as exc:
                    LOG.warning("Discord-Aktualisierung fehlgeschlagen: %s",type(exc).__name__)
            await asyncio.sleep(5)

    async def close(self):
        if self.publisher:
            self.publisher.cancel()
        await super().close()


class DiscordRunner:
    def __init__(self, store, token, channel_id, guild_id, registry=None):
        valid_legacy=str(channel_id).isdigit() and str(guild_id).isdigit()
        valid_clients=registry and any(str(c.get('discord_channel_id','')).isdigit() and str(c.get('discord_guild_id','')).isdigit() for c in registry.records())
        if not token or not (valid_legacy or valid_clients):
            raise ValueError('Discord: Token sowie Kanal/Server pro Spieler konfigurieren.')
        self.bot = VotingBot(store,channel_id,guild_id,registry)
        self.token, self.loop, self.thread = token, None, None

    def start(self):
        def run():
            async def connect():
                self.loop = asyncio.get_running_loop()
                async with self.bot:
                    await self.bot.start(self.token)
            try:
                asyncio.run(connect())
            except Exception as exc:
                LOG.error('Discord-Verbindung beendet: %s. Token/Berechtigungen pruefen.',type(exc).__name__)
        self.thread = threading.Thread(target=run,daemon=True,name='kr-discord')
        self.thread.start()

    def stop(self):
        if self.loop and self.loop.is_running():
            try:
                asyncio.run_coroutine_threadsafe(self.bot.close(),self.loop).result(timeout=10)
            except Exception:
                LOG.warning('Discord-Bot wird beendet.')
        if self.thread:
            self.thread.join(timeout=5)
