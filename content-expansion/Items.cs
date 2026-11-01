using System;
using System.Collections.Generic;
using AldaEngine;
using KillingRoom;
using HarmonyLib;

namespace KillingRoomCommunity.Content
{
    public sealed class ItemDefinition
    {
        public string Id, Name, Description, Icon;
        public bool Good;
        public CLootInfoBase.ELootQuality Quality;
        public int Price;

        public ItemDefinition(string id, string name, string description, string icon, bool good,
            CLootInfoBase.ELootQuality quality, int price)
        { Id = id; Name = name; Description = description; Icon = icon; Good = good; Quality = quality; Price = price; }
    }

    // Original code only. No copied game implementation, models or textures.
    public sealed class CommunityItem : COneOffItemBase
    {
        public CommunityItem(ItemDefinition definition)
            : base(definition.Id, false, definition.Good, EItemOnlineStatus.OnlineOrGame, 1)
        {
            textureName = definition.Icon;
            InitLootInfo(1, definition.Price, definition.Quality, CResourcesKR.pathToPickUpItem);
        }
    }

    public static class ItemCatalog
    {
        public const string Adrenaline = "KRCE_AdrenalineBattery";
        public const string Echo = "KRCE_EchoMagazine";
        public const string Relay = "KRCE_EmergencyRelay";
        public const string Overclock = "KRCE_OverheatedRelay";
        public const string Boots = "KRCE_LeadBoots";
        public const string Static = "KRCE_StaticCoil";

        public static readonly ItemDefinition[] Definitions = new ItemDefinition[] {
            new ItemDefinition(Adrenaline, "Adrenaline Battery", "Clearing a combat room grants +15% movement speed for 8 seconds.", "RedCow", true, CLootInfoBase.ELootQuality.rare, 3500),
            new ItemDefinition(Echo, "Echo Magazine", "Every sixth standard gun volley fires a free extra volley. Special weapons and melee are excluded.", "DeepPockets", true, CLootInfoBase.ELootQuality.rare, 4500),
            new ItemDefinition(Relay, "Emergency Relay", "After surviving a hit at 25% health or less, take 50% less damage for 4 seconds. Cooldown: 45 seconds.", "NanoBugs", true, CLootInfoBase.ELootQuality.legendary, 6000),
            new ItemDefinition(Overclock, "Overheated Relay", "+12% direct damage, but take 15% more damage. A cursed crowd favourite.", "BagOfCoke", false, CLootInfoBase.ELootQuality.rare, 2500),
            new ItemDefinition(Boots, "Lead Boots", "Lose 8% of the speed-stat range and gain 4 defense points.", "NanoShoes", false, CLootInfoBase.ELootQuality.normal, 1000),
            new ItemDefinition(Static, "Static Coil", "Each cleared combat room drains 5% of maximum armour. Health is not drained.", "SpikedCollar", false, CLootInfoBase.ELootQuality.normal, 1000)
        };

        public static ItemDefinition Find(string id)
        {
            foreach (ItemDefinition definition in Definitions) if (definition.Id == id) return definition;
            return null;
        }

        public static void Register(CConfigOneOffItem config, bool generate)
        {
            Dictionary<string, COneOffItemBase> items = (Dictionary<string, COneOffItemBase>)
                AccessTools.Field(typeof(CConfigOneOffItem), "items").GetValue(config);
            // A singleton can exist before its Awake/Init has populated vanilla
            // items. Keep that dictionary empty so the native initializer runs.
            if (!items.ContainsKey("Map")) return;
            foreach (ItemDefinition definition in Definitions)
            {
                if (items.ContainsKey(definition.Id)) continue;
                CommunityItem item = new CommunityItem(definition);
                if (definition.Id == Boots)
                {
                    item.bonuses.Add(COneOffItemBase.EStatType.Speed, -8);
                    item.bonuses.Add(COneOffItemBase.EStatType.Defense, 4);
                }
                config.AddItem(item);
            }
            if (!generate)
            {
                List<COneOffItemBase> pool = (List<COneOffItemBase>)AccessTools.Field(typeof(CConfigOneOffItem), "itemsForGenerate").GetValue(config);
                pool.RemoveAll(delegate(COneOffItemBase item) { return Find(item.itemIdentificator) != null; });
            }
        }
    }
}
