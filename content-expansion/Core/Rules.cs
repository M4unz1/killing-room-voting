using System;
using System.Collections.Generic;
using System.Globalization;

namespace KillingRoomCommunity.Content
{
    public enum Challenge { Off, GlassCannon, ArmsRoulette, Showtime, ChaosBroadcast }
    public enum EliteKind { Normal, Sprinter, Juggernaut, Medic }

    // No Unity dependencies: lifecycle, timing and persistence rules can be tested
    // without loading or executing the original game assemblies.
    public sealed class RunRules
    {
        public Challenge Profile;
        public uint RandomState;
        public uint RunSeed;
        public double Clock;
        public int QuickRooms;
        public int EchoCounter;
        public double AdrenalineUntil;
        public double ShieldUntil;
        public double RelayReadyAt;
        public bool RunStarted;
        public string ActiveRoom = "";
        public double RoomStartedAt;
        public readonly HashSet<string> Entered = new HashSet<string>();
        public readonly HashSet<string> Completed = new HashSet<string>();

        public RunRules(Challenge profile, uint seed)
        {
            Profile = profile;
            RunSeed = seed == 0 ? 0x9e3779b9u : seed;
            RandomState = RunSeed;
        }

        public uint NextRandom()
        {
            uint x = RandomState;
            x ^= x << 13; x ^= x >> 17; x ^= x << 5;
            RandomState = x;
            return x;
        }

        public void Tick(float delta)
        {
            if (!float.IsNaN(delta) && !float.IsInfinity(delta) && delta > 0)
                Clock += Math.Min(delta, 1f);
        }

        public bool EnterRoom(string key)
        {
            RunStarted = true;
            if (Completed.Contains(key) || !Entered.Add(key)) return false;
            ActiveRoom = key;
            RoomStartedAt = Clock;
            return true;
        }

        public bool CompleteRoom(string key, bool adrenaline, float showtimeSeconds)
        {
            if (!Entered.Contains(key) || !Completed.Add(key)) return false;
            if (Profile == Challenge.Showtime && key == ActiveRoom && Clock - RoomStartedAt <= showtimeSeconds)
                QuickRooms = Math.Min(QuickRooms + 1, 10);
            if (adrenaline) AdrenalineUntil = Clock + 8;
            if (ActiveRoom == key) ActiveRoom = "";
            return true;
        }

        public bool EchoShot(bool ownsItem, bool eligible, int interval)
        {
            if (!ownsItem || !eligible) return false;
            EchoCounter++;
            if (EchoCounter < Math.Max(2, interval)) return false;
            EchoCounter = 0;
            return true;
        }

        public bool ActivateRelay(bool ownsItem, float health, float maxHealth)
        {
            if (!ownsItem || health <= 0 || maxHealth <= 0 || health > maxHealth * .25f || Clock < RelayReadyAt)
                return false;
            ShieldUntil = Clock + 4;
            RelayReadyAt = Clock + 45;
            return true;
        }

        public bool ShowtimeOver(float limit)
        {
            return Profile == Challenge.Showtime && ActiveRoom.Length != 0 && Clock - RoomStartedAt > limit;
        }

        public int FloorMutator(int floor)
        {
            uint mixed = RunSeed ^ unchecked((uint)floor * 0x9e3779b9u);
            mixed ^= mixed >> 16; mixed *= 0x7feb352du; mixed ^= mixed >> 15;
            return (int)(mixed % 3);
        }

        public float Outgoing(int floor, bool overclock)
        {
            float value = Profile == Challenge.GlassCannon ? 1.35f : 1f;
            if (Profile == Challenge.Showtime) value *= 1f + QuickRooms * .02f;
            if (Profile == Challenge.ChaosBroadcast && FloorMutator(floor) == 2) value *= 1.2f;
            if (overclock) value *= 1.12f;
            return value;
        }

        public float Incoming(int floor, bool overclock, float showtimeSeconds)
        {
            float value = Profile == Challenge.GlassCannon ? 1.5f : 1f;
            if (ShowtimeOver(showtimeSeconds)) value *= 1.25f;
            if (Profile == Challenge.ChaosBroadcast)
            {
                if (FloorMutator(floor) == 1) value *= .85f;
                else if (FloorMutator(floor) == 2) value *= 1.15f;
            }
            if (overclock) value *= 1.15f;
            if (Clock < ShieldUntil) value *= .5f;
            return value;
        }

        public float PlayerSpeed(int floor)
        {
            float value = Clock < AdrenalineUntil ? 1.15f : 1f;
            if (Profile == Challenge.ChaosBroadcast && FloorMutator(floor) == 0) value *= 1.12f;
            return value;
        }

        public float EnemySpeed(int floor)
        {
            return Profile == Challenge.ChaosBroadcast && FloorMutator(floor) == 0 ? 1.15f : 1f;
        }

        public float EnemyHealth(int floor)
        {
            return Profile == Challenge.ChaosBroadcast && FloorMutator(floor) == 1 ? 1.25f : 1f;
        }

        public EliteKind ChooseElite(float chance)
        {
            float roll = (NextRandom() >> 8) / 16777216f;
            if (roll >= Math.Max(0, Math.Min(1, chance))) return EliteKind.Normal;
            return (EliteKind)(1 + NextRandom() % 3);
        }

        public int ChooseSlot(int[] owned, int current)
        {
            List<int> alternatives = new List<int>();
            foreach (int slot in owned) if (slot != current && !alternatives.Contains(slot)) alternatives.Add(slot);
            if (alternatives.Count == 0) return current;
            return alternatives[(int)(NextRandom() % (uint)alternatives.Count)];
        }

        public static float HealedHealth(float current, float maximum, float fraction)
        {
            if (current <= 0 || maximum <= 0) return current;
            return Math.Min(maximum, current + maximum * Math.Max(0, fraction));
        }
    }

    public static class StateCodec
    {
        private static readonly CultureInfo Culture = CultureInfo.InvariantCulture;

        public static string Write(RunRules rules, string saveHash)
        {
            // Lists contain base64 room keys so delimiters in Unity scene/object
            // names cannot corrupt the state. All times are remaining durations.
            return "KRCE1\n" + saveHash + "\n" + ((int)rules.Profile).ToString(Culture) + "\n" +
                rules.RandomState.ToString(Culture) + "\n" + rules.RunSeed.ToString(Culture) + "\n" + rules.QuickRooms.ToString(Culture) + "\n" +
                rules.EchoCounter.ToString(Culture) + "\n" + Remaining(rules.AdrenalineUntil, rules.Clock) + "\n" +
                Remaining(rules.ShieldUntil, rules.Clock) + "\n" + Remaining(rules.RelayReadyAt, rules.Clock) + "\n" +
                Pack(rules.Entered) + "\n" + Pack(rules.Completed) + "\n";
        }

        private static string Remaining(double until, double now)
        {
            return Math.Max(0, until - now).ToString("R", Culture);
        }

        private static string Pack(IEnumerable<string> values)
        {
            List<string> encoded = new List<string>();
            foreach (string value in values) encoded.Add(Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(value)));
            encoded.Sort(StringComparer.Ordinal);
            return string.Join(",", encoded.ToArray());
        }

        private static void Unpack(string line, HashSet<string> target)
        {
            if (line.Length == 0) return;
            string[] values = line.Split(',');
            if (values.Length > 2000) throw new FormatException("Too many room keys.");
            foreach (string value in values)
            {
                string text = System.Text.Encoding.UTF8.GetString(Convert.FromBase64String(value));
                if (text.Length > 512) throw new FormatException("Room key too long.");
                target.Add(text);
            }
        }

        public static bool TryRead(string text, string saveHash, out RunRules rules)
        {
            rules = null;
            if (text == null || text.Length > 1000000) return false;
            try
            {
                string[] lines = text.Replace("\r", "").Split('\n');
                if (lines.Length < 12 || lines[0] != "KRCE1" || lines[1] != saveHash) return false;
                int profile = int.Parse(lines[2], Culture);
                if (profile < 0 || profile > (int)Challenge.ChaosBroadcast) return false;
                RunRules loaded = new RunRules((Challenge)profile, uint.Parse(lines[4], Culture));
                loaded.RandomState = uint.Parse(lines[3], Culture);
                if (loaded.RandomState == 0) return false;
                loaded.QuickRooms = int.Parse(lines[5], Culture);
                loaded.EchoCounter = int.Parse(lines[6], Culture);
                loaded.AdrenalineUntil = double.Parse(lines[7], Culture);
                loaded.ShieldUntil = double.Parse(lines[8], Culture);
                loaded.RelayReadyAt = double.Parse(lines[9], Culture);
                if (loaded.QuickRooms < 0 || loaded.QuickRooms > 10 || loaded.EchoCounter < 0 || loaded.EchoCounter > 100) return false;
                foreach (double value in new double[] { loaded.AdrenalineUntil, loaded.ShieldUntil, loaded.RelayReadyAt })
                    if (double.IsNaN(value) || double.IsInfinity(value) || value < 0 || value > 45) return false;
                Unpack(lines[10], loaded.Entered); Unpack(lines[11], loaded.Completed);
                foreach (string key in loaded.Completed) if (!loaded.Entered.Contains(key)) return false;
                loaded.RunStarted = true;
                rules = loaded;
                return true;
            }
            catch (Exception error)
            {
                if (error is FormatException || error is OverflowException || error is ArgumentException) return false;
                throw;
            }
        }
    }
}
