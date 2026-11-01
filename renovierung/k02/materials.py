"""Volume equivalents for one material; table factors are not dry densities."""
import math


def balance(bank_m3, fill_m3, loose_factor=1.05, compacted_factor=0.89):
    if any(not math.isfinite(v) for v in (bank_m3,fill_m3,loose_factor,compacted_factor)):
        raise ValueError('Nonfinite material input')
    if min(bank_m3,fill_m3)<0 or min(loose_factor,compacted_factor)<=0:
        raise ValueError('Invalid material input')
    need_bank=fill_m3/compacted_factor
    return {'bank_m3':bank_m3,'stockpiled_loose_m3':bank_m3*loose_factor,
            'compacted_available_m3':bank_m3*compacted_factor,'fill_m3':fill_m3,
            'loose_needed_m3':need_bank*loose_factor,
            'import_bank_equivalent_m3':max(0,need_bank-bank_m3),
            'remaining_loose_m3':max(0,bank_m3-need_bank)*loose_factor,
            'returned_bank_equivalent_m3':min(bank_m3,need_bank),
            'loose_factor':loose_factor,'compacted_factor':compacted_factor,
            'mass_kg':None,'basis':'SAME_MATERIAL_VOLUME_EQUIVALENTS_NOT_DRY_DENSITIES'}
