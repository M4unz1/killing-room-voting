using System;
using HarmonyLib;
using KillingRoom;
using UnityEngine;

namespace KillingRoomCommunity.Content
{
    [HarmonyPatch(typeof(CConfigOneOffItem), "Init")]
    internal static class RegisterItemsHook
    {
        private static void Postfix(CConfigOneOffItem __instance)
        {
            try { ItemCatalog.Register(__instance, ContentPlugin.Instance.GenerateItems.Value); }
            catch (Exception error) { ContentPlugin.Report(error); }
        }
    }

    [HarmonyPatch(typeof(COneOffItemBase), "get_itemName")]
    internal static class ItemNameHook
    {
        private static bool Prefix(COneOffItemBase __instance, ref string __result)
        {
            ItemDefinition definition = ItemCatalog.Find(__instance.itemIdentificator);
            if (definition == null) return true;
            __result = definition.Name; return false;
        }
    }

    [HarmonyPatch(typeof(COneOffItemBase), "get_itemDescription")]
    internal static class ItemDescriptionHook
    {
        private static bool Prefix(COneOffItemBase __instance, ref string __result)
        {
            ItemDefinition definition = ItemCatalog.Find(__instance.itemIdentificator);
            if (definition == null) return true;
            __result = definition.Description; return false;
        }
    }

    [HarmonyPatch(typeof(CPlayerInfoPersistent), "ResetStats")]
    internal static class NewRunHook { private static void Postfix() { ContentPlugin.NewRun(); } }

    [HarmonyPatch(typeof(CEnemyManager), "PlayerInRoom")]
    internal static class CombatEntryHook
    {
        private static void Prefix(CEnemyManager __instance)
        {
            try { ContentPlugin.EnterCombat(__instance); }
            catch (Exception error) { ContentPlugin.Report(error); }
        }
    }

    [HarmonyPatch(typeof(CBaseRoomScript), "SetRoomAsCompleted")]
    internal static class CombatCompleteHook
    {
        private static void Prefix(CBaseRoomScript __instance, ref bool __state) { __state = !__instance.roomCompleted; }
        private static void Postfix(CBaseRoomScript __instance, bool __state)
        {
            if (!__state || !__instance.roomCompleted) return;
            try { ContentPlugin.CompleteCombat(__instance); }
            catch (Exception error) { ContentPlugin.Report(error); }
        }
    }

    [HarmonyPatch(typeof(CPlayerDamageHandler), "Damage")]
    internal static class PlayerDamageHook
    {
        internal static void Prefix(CPlayerDamageHandler __instance, ref CDamageHandler.DamageInfo pDamageInfo)
        {
            if (!ContentPlugin.Playing || pDamageInfo.damage <= 0) return;
            pDamageInfo.damage *= ContentPlugin.Rules.Incoming(ContentPlugin.Floor, ContentPlugin.Owns(ItemCatalog.Overclock), ContentPlugin.Instance.ShowtimeSeconds.Value);
        }
        internal static void Postfix(CPlayerDamageHandler __instance)
        {
            if (!ContentPlugin.Playing) return;
            if (ContentPlugin.Rules.ActivateRelay(ContentPlugin.Owns(ItemCatalog.Relay), __instance.CurrentHealth, __instance.MaxHealth))
                ContentPlugin.Notice("Emergency Relay: shield active for 4 seconds.");
        }
    }

    [HarmonyPatch(typeof(CPlayerDamageHandler), "DamageRaw")]
    internal static class RawPlayerDamageHook
    {
        private static void Prefix(CPlayerDamageHandler __instance, ref CDamageHandler.DamageInfo pDamageInfo) { PlayerDamageHook.Prefix(__instance, ref pDamageInfo); }
        private static void Postfix(CPlayerDamageHandler __instance) { PlayerDamageHook.Postfix(__instance); }
    }

    [HarmonyPatch(typeof(CDamageHandler), "Damage")]
    internal static class EnemyDamageHook
    {
        private static void Prefix(CDamageHandler __instance, ref CDamageHandler.DamageInfo pDamageInfo)
        {
            if (!ContentPlugin.Playing || pDamageInfo.damage <= 0 || __instance is CPlayerDamageHandler) return;
            CEnemyBase enemy = __instance.GetComponent<CEnemyBase>();
            if (enemy == null) return;
            Transform player = ContentPlugin.Player.transform;
            if (pDamageInfo.source != null && (pDamageInfo.source == player || pDamageInfo.source.IsChildOf(player)))
                pDamageInfo.damage *= ContentPlugin.Rules.Outgoing(ContentPlugin.Floor, ContentPlugin.Owns(ItemCatalog.Overclock));
            EliteTag tag = enemy.GetComponent<EliteTag>();
            if (tag != null && tag.Configured && tag.Kind == EliteKind.Juggernaut) pDamageInfo.damage *= .8f;
        }
    }

    [HarmonyPatch(typeof(CFirstPersonController), "GetSpeedByState")]
    internal static class PlayerMovementHook
    {
        private static void Postfix(ref float __result)
        { if (ContentPlugin.Playing) __result *= ContentPlugin.Rules.PlayerSpeed(ContentPlugin.Floor); }
    }

    [HarmonyPatch(typeof(CEnemyMotorBase), "Move")]
    internal static class EnemyMovementHook
    {
        private static void Prefix(CEnemyMotorBase __instance, ref float pSpeedModificator)
        {
            if (!ContentPlugin.Playing) return;
            EliteTag tag = __instance.GetComponentInParent<EliteTag>();
            if (tag != null && tag.Configured) pSpeedModificator *= tag.Speed;
        }
    }

    [HarmonyPatch(typeof(CPlayerWeapon), "CreateProjectile")]
    internal static class EchoProjectileHook
    {
        private static void Postfix(CPlayerWeapon __instance)
        {
            try { ContentPlugin.ProjectileFired(__instance); }
            catch (Exception error) { ContentPlugin.Report(error); }
        }
    }

    [HarmonyPatch(typeof(CPlayerSerializer), "Serialize")]
    internal static class SaveHook
    {
        private static void Prefix()
        { try { ContentPlugin.Instance.SaveBackup(); } catch (Exception error) { ContentPlugin.Report(error); } }
        private static void Postfix()
        { try { ContentPlugin.Instance.AfterSave(); } catch (Exception error) { ContentPlugin.Report(error); } }
    }

    [HarmonyPatch(typeof(CPlayerSerializer), "Deserialize")]
    internal static class LoadHook
    {
        private static void Prefix()
        { try { ContentPlugin.Instance.BeforeLoad(); } catch (Exception error) { ContentPlugin.Report(error); } }
        private static void Postfix(bool __result)
        { ContentPlugin.Instance.AfterLoad(__result); }
    }
}
