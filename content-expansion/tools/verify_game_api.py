"""Static ABI checks only. Does not load or execute the provided game DLL."""
import argparse
import hashlib
import json
from pathlib import Path
import dnfile

HOOKS = {
    'KillingRoom.CConfigOneOffItem': {'Init': [], 'AddItem': ['pItem']},
    'KillingRoom.COneOffItemBase': {'get_itemName': [], 'get_itemDescription': []},
    'KillingRoom.CPlayerInfoPersistent': {'ResetStats': []},
    'CEnemyManager': {'PlayerInRoom': [], 'GetRoomEnemies': []},
    'CBaseRoomScript': {'SetRoomAsCompleted': []},
    'KillingRoom.CPlayerDamageHandler': {'Damage': ['pDamageInfo'], 'DamageRaw': ['pDamageInfo']},
    'KillingRoom.CDamageHandler': {'Damage': ['pDamageInfo']},
    'KillingRoom.CFirstPersonController': {'GetSpeedByState': []},
    'KillingRoom.CEnemyMotorBase': {'Move': ['pSpeedModificator']},
    'KillingRoom.CPlayerWeapon': {'CreateProjectile': []},
    'KillingRoom.CPlayerSerializer': {'Serialize': [], 'Deserialize': []},
}


def verify(path):
    pe = dnfile.dnPE(str(path))
    types = {'.'.join(filter(None, [str(t.TypeNamespace), str(t.TypeName)])): t for t in pe.net.mdtables.TypeDef}
    result = []
    for name, methods in HOOKS.items():
        for method, names in methods.items():
            matches = [entry.row for entry in types[name].MethodList if str(entry.row.Name) == method]
            if len(matches) != 1:
                raise ValueError(name+'::'+method+' is missing or ambiguous.')
            row = matches[0]
            parameters = [str(item.row.Name) for item in row.ParamList if item.row.Sequence > 0]
            if parameters != names:
                raise ValueError(name+'::'+method+' parameter names differ.')
            result.append({'type': name, 'method': method, 'signature': row.Signature.value.hex(), 'parameters': parameters})
    return {'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'verified_members': result}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('assembly', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.assembly), indent=2))
