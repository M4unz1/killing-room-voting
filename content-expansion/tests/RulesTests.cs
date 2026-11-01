using System;
using System.Globalization;
using System.Collections.Generic;
using KillingRoomCommunity.Content;

public static class RulesTests
{
    private static int passed;
    private static void Check(bool result, string label)
    { if (!result) throw new Exception(label); passed++; Console.WriteLine("PASS: " + label); }
    private static bool Close(double a, double b) { return Math.Abs(a - b) < .0001; }

    public static void Main()
    {
        RunRules r = new RunRules(Challenge.Showtime, 42);
        Check(r.EnterRoom("1:room"), "first combat entry starts one timer");
        for (int i = 0; i < 20; i++) r.Tick(1);
        Check(!r.EnterRoom("1:room") && Close(r.RoomStartedAt, 0), "re-entry does not reset the time target");
        Check(r.CompleteRoom("1:room", true, 45) && r.QuickRooms == 1, "quick completion awards one challenge bonus");
        double expiry = r.AdrenalineUntil;
        Check(!r.CompleteRoom("1:room", true, 45) && r.QuickRooms == 1 && r.AdrenalineUntil == expiry, "duplicate completion cannot farm boosts");
        Check(!r.CompleteRoom("unknown", true, 45), "completion without combat entry is ignored");
        Check(r.EnterRoom("2:room"), "same room name on another floor is independent");
        for (int i = 0; i < 46; i++) r.Tick(1);
        Check(r.ShowtimeOver(45) && Close(r.Incoming(2, false, 45), 1.25), "overtime applies a bounded room penalty");
        r.CompleteRoom("2:room", false, 45);
        Check(r.QuickRooms == 1 && !r.ShowtimeOver(45), "slow completion removes penalty without awarding a quick bonus");
        double now = r.Clock;
        r.Tick(0); r.Tick(-1); r.Tick(float.NaN); r.Tick(float.PositiveInfinity);
        Check(r.Clock == now, "paused or invalid time does not advance timers");

        r = new RunRules(Challenge.GlassCannon, 7);
        Check(!r.ActivateRelay(true, 0, 100), "relay cannot revive a dead player");
        Check(!r.ActivateRelay(true, 26, 100), "relay respects the low-health threshold");
        Check(r.ActivateRelay(true, 25, 100), "survived critical health activates the shield");
        Check(Close(r.Incoming(1, false, 45), .75), "shield composes with challenge damage rather than replacing it");
        for (int i = 0; i < 5; i++) r.Tick(1);
        Check(Close(r.Incoming(1, false, 45), 1.5) && !r.ActivateRelay(true, 20, 100), "shield expires and cooldown prevents permanent immunity");
        for (int i = 0; i < 40; i++) r.Tick(1);
        Check(r.ActivateRelay(true, 20, 100), "relay becomes available after its cooldown");
        Check(!r.EchoShot(false, true, 6) && !r.EchoShot(true, false, 6) && r.EchoCounter == 0, "non-owned or ineligible weapons do not build echo progress");
        bool early = false;
        for (int i = 0; i < 5; i++) early |= r.EchoShot(true, true, 6);
        Check(!early && r.EchoShot(true, true, 6) && r.EchoCounter == 0, "sixth eligible volley produces one echo");

        r = new RunRules(Challenge.ChaosBroadcast, 123);
        int mutator = r.FloorMutator(4);
        for (int i = 0; i < 50; i++) r.ChooseElite(.5f);
        Check(r.FloorMutator(4) == mutator, "elite RNG cannot change a floor mutator mid-floor");
        HashSet<int> outcomes = new HashSet<int>();
        for (int i = 1; i < 30; i++) outcomes.Add(r.FloorMutator(i));
        Check(outcomes.Count == 3, "seeded floors can select all three mutators");
        bool bad = false;
        for (int i = 0; i < 100; i++) bad |= r.ChooseElite(0) != EliteKind.Normal;
        Check(!bad, "zero elite chance leaves every enemy normal");
        Check(r.ChooseSlot(new int[] { 0 }, 0) == 0, "roulette preserves the only available weapon");
        for (int i = 0; i < 100; i++) if (r.ChooseSlot(new int[] { 0, 1, 2 }, 1) == 1) throw new Exception("roulette repeated current slot");
        Check(true, "roulette selects an owned alternative when one exists");
        Check(Close(RunRules.HealedHealth(98, 100, .06f), 100), "medic healing never exceeds maximum health");
        Check(Close(RunRules.HealedHealth(0, 100, .06f), 0), "medics never resurrect a dead enemy");

        r.EnterRoom("3:room,unicode-ä"); r.CompleteRoom("3:room,unicode-ä", true, 45);
        r.EchoCounter = 3; r.QuickRooms = 5; r.ActivateRelay(true, 15, 100);
        for (int i = 0; i < 2; i++) r.Tick(1);
        CultureInfo old = CultureInfo.CurrentCulture;
        CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo("de-DE");
        string saved = StateCodec.Write(r, "same-save");
        RunRules loaded;
        Check(StateCodec.TryRead(saved, "same-save", out loaded), "saved state round-trips under German number formatting");
        Check(loaded.Profile == r.Profile && loaded.RunSeed == r.RunSeed && loaded.RandomState == r.RandomState && loaded.EchoCounter == 3 && loaded.QuickRooms == 5, "challenge, seed and item progress survive a restart");
        Check(loaded.Completed.Contains("3:room,unicode-ä") && !loaded.EnterRoom("3:room,unicode-ä"), "room rewards remain deduplicated after loading");
        Check(Close(loaded.ShieldUntil, 2) && Close(loaded.RelayReadyAt, 43) && Close(loaded.AdrenalineUntil, 6), "remaining durations are rebased to the new game clock");
        Check(!StateCodec.TryRead(saved, "other-save", out loaded), "stale sidecars cannot attach to another saved run");
        Check(!StateCodec.TryRead("broken", "same-save", out loaded), "truncated state is rejected");
        string[] lines = saved.Split('\n'); lines[8] = "NaN";
        Check(!StateCodec.TryRead(string.Join("\n", lines), "same-save", out loaded), "non-finite timer values are rejected");
        lines = saved.Split('\n'); lines[2] = "999";
        Check(!StateCodec.TryRead(string.Join("\n", lines), "same-save", out loaded), "unknown challenges cannot enter a loaded run");
        CultureInfo.CurrentCulture = old;
        Console.WriteLine("Passed " + passed + " lifecycle checks.");
    }
}
