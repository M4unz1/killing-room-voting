using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Security.Cryptography;
using AldaEngine;
using BepInEx;
using BepInEx.Configuration;
using HarmonyLib;
using KillingRoom;
using UnityEngine;

namespace KillingRoomCommunity.Content
{
    [BepInPlugin("m4unz1.killingroom.content", "Killing Room Community Content", "0.1.0")]
    public sealed class ContentPlugin : BaseUnityPlugin
    {
        internal static ContentPlugin Instance;
        internal ConfigEntry<Challenge> NextChallenge;
        internal ConfigEntry<bool> GenerateItems, Elites, Hud, TestKeys;
        internal ConfigEntry<float> EliteChance, ShowtimeSeconds;
        internal static RunRules Rules = new RunRules(Challenge.Off, 1);
        private Harmony patches;
        private bool ready;
        private bool echoBusy;
        private string scene = "";
        private static readonly MethodInfo FireExtra = AccessTools.Method(typeof(CPlayerWeapon), "CreateProjectile", Type.EmptyTypes);
        private RunRules pendingLoad;
        private string lastNotice = "";

        internal static CGameController Game
        {
            get { return MonoSingleton<CGameController>.IsNull ? null : MonoSingleton<CGameController>.GetInstance(); }
        }

        internal static CPlayerScript Player
        {
            get { CGameController game = Game; return game == null || game.playerObject == null ? null : game.playerScript; }
        }

        internal static bool Playing
        {
            get { return CKillingRoomStatic.IsMainGame() && !CKillingRoomStatic.IsTutorial() && Game != null && Game.loadCompleteGame && Player != null; }
        }

        internal static int Floor { get { return Player == null ? 1 : Player.playerInfo.actualFloor; } }
        internal static bool Owns(string id)
        {
            CPlayerScript player = Player;
            return player != null && player.playerInfo.itemManager.HavePlayerItemWithidentificator(id);
        }

        private void Awake()
        {
            Instance = this;
            NextChallenge = Config.Bind("Challenges", "NextRun", Challenge.Off, "Challenge for NEW runs. F6 cycles this in the main menu.");
            ShowtimeSeconds = Config.Bind("Challenges", "ShowtimeSeconds", 45f,
                new ConfigDescription("Combat-room time target, excluding bosses and puzzle rooms.", new AcceptableValueRange<float>(10, 300)));
            GenerateItems = Config.Bind("Items", "GenerateNewItems", true, "Add six items to native loot and voting pools. Existing saved items stay registered when false.");
            Elites = Config.Bind("Enemies", "EnableVariants", true, "Allow variants of regular enemies. Bosses and special AI types are excluded.");
            EliteChance = Config.Bind("Enemies", "VariantChance", .18f,
                new ConfigDescription("Chance that a regular enemy becomes an elite variant.", new AcceptableValueRange<float>(0, .5f)));
            Hud = Config.Bind("Interface", "ShowHud", true, "F8 toggles the content HUD and elite labels.");
            TestKeys = Config.Bind("Testing", "EnableItemGrantKey", false, "Optional F7 grants the three positive items during a run. Disabled by default.");
            string path = Path.Combine(Application.dataPath, "Managed/Assembly-CSharp.dll");
            if (!BuildInfo.SupportedGameHashes.Contains(Hash(path)))
            {
                Logger.LogError("Unsupported Assembly-CSharp.dll. No gameplay hooks installed. Use the analyzed build or a supported voting patch.");
                return;
            }
            patches = new Harmony("m4unz1.killingroom.content");
            try
            {
                SaveBackup();
                patches.PatchAll(typeof(ContentPlugin).Assembly);
                if (!MonoSingleton<CConfigOneOffItem>.IsNull)
                    ItemCatalog.Register(MonoSingleton<CConfigOneOffItem>.GetInstance(), GenerateItems.Value);
                ready = true;
                Logger.LogInfo("Community Content 0.1.0 alpha loaded: 4 challenges, 6 items, 3 enemy variants. Game DLL is unchanged.");
            }
            catch (Exception error)
            {
                patches.UnpatchSelf();
                Logger.LogError("Content startup failed; hooks removed: " + error);
            }
        }

        private void Update()
        {
            if (!ready) return;
            if (Input.GetKeyDown(KeyCode.F8)) { Hud.Value = !Hud.Value; Config.Save(); }
            string currentScene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            if (scene != currentScene)
            {
                scene = currentScene;
                EliteTag.Tags.RemoveWhere(delegate(EliteTag tag) { return tag == null; });
                if (!CKillingRoomStatic.IsMainGame()) Rules.ActiveRoom = "";
            }
            if (!CKillingRoomStatic.IsMainGame() && Input.GetKeyDown(KeyCode.F6))
            {
                NextChallenge.Value = (Challenge)(((int)NextChallenge.Value + 1) % 5);
                Config.Save();
            }
            if (!Playing || Player.playerDamageHandler.IsDead()) return;
            if (!Rules.RunStarted) Rules.Profile = NextChallenge.Value;
            Rules.Tick(Time.deltaTime);
            if (TestKeys.Value && Input.GetKeyDown(KeyCode.F7))
            {
                foreach (ItemDefinition definition in ItemCatalog.Definitions)
                    if (definition.Good) Player.playerInfo.itemManager.AddItem(Game.itemConfig.GetItem(definition.Id), false);
                Notice("Test items granted. This is a modded run.");
            }
        }

        private void OnGUI()
        {
            if (!ready || !Hud.Value) return;
            if (!CKillingRoomStatic.IsMainGame())
            {
                GUI.Box(new Rect(12, Screen.height - 68, 500, 54), "Community Content (alpha) | Next run: " + NextChallenge.Value + "\nF6: choose challenge   F8: hide/show HUD");
                return;
            }
            if (!Playing) return;
            string extra = "";
            if (Rules.Profile == Challenge.Showtime && Rules.ActiveRoom.Length > 0)
                extra = " | Timer: " + Math.Max(0, ShowtimeSeconds.Value - (Rules.Clock - Rules.RoomStartedAt)).ToString("0") + "s";
            if (Rules.Clock < Rules.AdrenalineUntil) extra += " | Adrenaline";
            if (Rules.Clock < Rules.ShieldUntil) extra += " | Shield";
            if (Rules.Profile == Challenge.ChaosBroadcast)
                extra += " | " + new string[] { "Turbo", "Iron Broadcast", "Glass Air" }[Rules.FloorMutator(Floor)];
            GUI.Box(new Rect(12, 12, Math.Min(700, Screen.width - 24), 52), "Community Content | " + Rules.Profile + extra + "\n" + lastNotice);
            Camera camera = Camera.main;
            if (camera == null) return;
            foreach (EliteTag tag in EliteTag.Tags)
            {
                if (tag == null || !tag.Configured || tag.Kind == EliteKind.Normal || !tag.Alive) continue;
                Vector3 screen = camera.WorldToScreenPoint(tag.transform.position + Vector3.up * 2.2f);
                if (screen.z <= 0 || screen.x < 0 || screen.x > Screen.width || screen.y < 0 || screen.y > Screen.height) continue;
                Color old = GUI.color;
                GUI.color = tag.Kind == EliteKind.Sprinter ? new Color(1, .55f, .3f) : tag.Kind == EliteKind.Medic ? Color.cyan : Color.yellow;
                GUI.Label(new Rect(screen.x - 70, Screen.height - screen.y - 24, 140, 24), tag.Kind.ToString());
                GUI.color = old;
            }
        }

        internal static void Notice(string text)
        {
            if (Instance == null) return;
            Instance.lastNotice = text;
            Instance.Logger.LogInfo(text);
        }

        internal static void NewRun()
        {
            if (Instance == null) return;
            Rules = new RunRules(Instance.NextChallenge.Value, BitConverter.ToUInt32(Guid.NewGuid().ToByteArray(), 0));
            Instance.pendingLoad = null;
            Notice("New run prepared. Challenge locks when combat starts.");
        }

        internal static string RoomKey(CBaseRoomScript room)
        {
            return Floor.ToString() + ":" + room.roomName;
        }

        internal static bool CombatRoom(CBaseRoomScript room)
        {
            return room != null && room.roomType == CGenerateLevel.ERoomType.fightRoom && !CKillingRoomStatic.IsTutorial();
        }

        internal static void EnterCombat(CEnemyManager manager)
        {
            if (Instance == null || !Playing) return;
            CBaseRoomScript room = manager.baseRoomScript;
            if (!CombatRoom(room) || room.roomCompleted || manager.GetRoomEnemies().Count == 0) return;
            if (!Rules.RunStarted) Rules.Profile = Instance.NextChallenge.Value;
            Rules.EnterRoom(RoomKey(room));
            foreach (SEnemyBase native in manager.GetRoomEnemies())
            {
                CEnemyAIBase ai = native.enemyScript as CEnemyAIBase;
                // Specialized bosses, resurrecting enemies and their states need
                // separate integration; the first alpha deliberately excludes them.
                if (ai == null || ai.GetType() != typeof(CEnemyAIBase) || ai.EnemyClass == CEnemyAIBase.EEnymyClass.Snowman || ai.DamageHandler.IsDead()) continue;
                EliteTag tag = ai.GetComponent<EliteTag>();
                if (tag == null) tag = ai.gameObject.AddComponent<EliteTag>();
                EliteKind kind = tag.Assigned ? tag.Kind : Instance.Elites.Value ? Rules.ChooseElite(Instance.EliteChance.Value) : EliteKind.Normal;
                tag.Configure(ai, manager, kind);
            }
        }

        internal static void CompleteCombat(CBaseRoomScript room)
        {
            if (Instance == null || !Playing || !CombatRoom(room)) return;
            if (!Rules.CompleteRoom(RoomKey(room), Owns(ItemCatalog.Adrenaline), Instance.ShowtimeSeconds.Value)) return;
            if (Owns(ItemCatalog.Static)) Player.playerDamageHandler.vest = Mathf.Max(0, Player.playerDamageHandler.vest - CConfigGame.PlayerVestMaxValue * .05f);
            if (Rules.Profile == Challenge.ArmsRoulette)
            {
                CPlayerWeaponsController weapons = Player.weaponController;
                List<int> slots = new List<int>();
                for (int i = 0; i < weapons.weaponSlots.Count; i++) if ((int)weapons.weaponSlots[i] > 0) slots.Add(i);
                int selected = Rules.ChooseSlot(slots.ToArray(), weapons.currentSlotIndex);
                if (selected != weapons.currentSlotIndex) weapons.ActivateSlot(selected);
            }
            Notice("Combat room cleared. " + (Rules.Profile == Challenge.Showtime ? "Showtime bonuses: " + Rules.QuickRooms : ""));
        }

        internal static void ProjectileFired(CPlayerWeapon weapon)
        {
            ContentPlugin plugin = Instance;
            if (plugin == null || !Playing || plugin.echoBusy || weapon.isMeleeWeapon || weapon.projectilePrefab == null) return;
            // Patch only the ordinary ray-projectile implementation. Specialized
            // frost/scythe projectiles are not recursively re-fired.
            if (AccessTools.Method(weapon.GetType(), "CreateProjectile", Type.EmptyTypes).DeclaringType != typeof(CPlayerWeapon)) return;
            if (!Rules.EchoShot(Owns(ItemCatalog.Echo), true, 6)) return;
            plugin.echoBusy = true;
            try { FireExtra.Invoke(weapon, new object[0]); }
            finally { plugin.echoBusy = false; }
        }

        internal static string Hash(string path)
        {
            using (SHA256 sha = SHA256.Create())
            using (FileStream file = File.OpenRead(path))
                return BitConverter.ToString(sha.ComputeHash(file)).Replace("-", "").ToLowerInvariant();
        }

        internal void SaveBackup()
        {
            string path = CPlayerSerializer.Filepath;
            string backup = path + ".krce-original.bak";
            string marker = path + ".krce-backup-status";
            if (File.Exists(marker)) return;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            if (File.Exists(path) && !File.Exists(backup)) File.Copy(path, backup, false);
            File.WriteAllText(marker, File.Exists(backup) ? "Initial save backed up.\n" : "No save existed at first content-mod startup.\n");
        }

        internal void BeforeLoad()
        {
            SaveBackup();
            pendingLoad = null;
            string path = CPlayerSerializer.Filepath;
            string sidecar = path + ".krce-state";
            if (File.Exists(path) && File.Exists(sidecar))
            {
                RunRules restored;
                if (new FileInfo(sidecar).Length <= 1000000 && StateCodec.TryRead(File.ReadAllText(sidecar), Hash(path), out restored)) pendingLoad = restored;
            }
        }

        internal void AfterLoad(bool success)
        {
            if (success && pendingLoad != null) Rules = pendingLoad;
            pendingLoad = null;
        }

        internal void AfterSave()
        {
            string path = CPlayerSerializer.Filepath;
            if (!File.Exists(path)) return;
            string target = path + ".krce-state";
            string temp = target + ".tmp";
            File.WriteAllText(temp, StateCodec.Write(Rules, Hash(path)));
            if (File.Exists(target)) File.Replace(temp, target, null);
            else File.Move(temp, target);
        }

        private void OnDestroy()
        {
            if (patches != null) patches.UnpatchSelf();
            if (Instance == this) Instance = null;
        }

        internal static void Report(Exception error)
        {
            if (Instance != null) Instance.Logger.LogError(error);
        }
    }

    public sealed class EliteTag : MonoBehaviour
    {
        internal static readonly HashSet<EliteTag> Tags = new HashSet<EliteTag>();
        internal CEnemyAIBase Enemy;
        internal CEnemyManager Manager;
        internal EliteKind Kind;
        internal bool Configured;
        internal bool Assigned;
        private float originalMax;
        private float factor = 1;
        private double nextHeal;
        internal bool Alive { get { return Enemy != null && Enemy.IsActive && !Enemy.DamageHandler.IsDead(); } }
        internal float Speed { get { return (Kind == EliteKind.Sprinter ? 1.35f : Kind == EliteKind.Juggernaut ? .75f : 1f) * ContentPlugin.Rules.EnemySpeed(ContentPlugin.Floor); } }

        internal void Configure(CEnemyAIBase enemy, CEnemyManager manager, EliteKind kind)
        {
            if (Configured) return;
            Enemy = enemy; Manager = manager; Kind = kind;
            originalMax = enemy.DamageHandler.MaxHealth;
            factor = (kind == EliteKind.Sprinter ? .8f : kind == EliteKind.Juggernaut ? 1.8f : kind == EliteKind.Medic ? 1.15f : 1f) * ContentPlugin.Rules.EnemyHealth(ContentPlugin.Floor);
            enemy.DamageHandler.MaxHealth = originalMax * factor;
            enemy.DamageHandler.CurrentHealth *= factor;
            nextHeal = ContentPlugin.Rules.Clock + 4;
            Configured = true; Assigned = true; Tags.Add(this);
        }

        private void Update()
        {
            if (!Configured || Kind != EliteKind.Medic || !Alive || Enemy.isFreezed || !ContentPlugin.Playing || Manager == null) return;
            if (ContentPlugin.Rules.Clock < nextHeal) return;
            nextHeal = ContentPlugin.Rules.Clock + 4;
            foreach (SEnemyBase member in Manager.GetRoomEnemies())
            {
                CEnemyAIBase ally = member.enemyScript as CEnemyAIBase;
                if (ally == null || ally == Enemy || ally.GetType() != typeof(CEnemyAIBase) || ally.EnemyClass == CEnemyAIBase.EEnymyClass.Snowman || !ally.IsActive || ally.DamageHandler.IsDead()) continue;
                if ((ally.transform.position - transform.position).sqrMagnitude > 36) continue;
                CDamageHandler health = ally.DamageHandler;
                health.CurrentHealth = RunRules.HealedHealth(health.CurrentHealth, health.MaxHealth, .06f);
            }
        }

        private void OnDisable()
        {
            // Room optimization can disable and later re-enable the same object.
            // Undo only our scaling, preserving its health ratio and death state.
            if (Configured && Enemy != null && Enemy.DamageHandler != null)
            {
                Enemy.DamageHandler.MaxHealth = originalMax;
                if (factor > 0) Enemy.DamageHandler.CurrentHealth /= factor;
            }
            Configured = false;
            Tags.Remove(this);
        }

        private void OnDestroy() { Tags.Remove(this); }
    }
}
