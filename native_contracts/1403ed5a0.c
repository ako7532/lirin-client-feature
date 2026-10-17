
undefined8 FUN_1403ed5a0(ulonglong param_1)

{
  longlong lVar1;
  ulonglong uVar2;

  uVar2 = DAT_147cd2eb0 &
          ((((param_1 & 0xff ^ 0xcbf29ce484222325) * 0x100000001b3 ^ param_1 >> 8 & 0xff) *
            0x100000001b3 ^ param_1 >> 0x10 & 0xff) * 0x100000001b3 ^ (param_1 & 0xffffffff) >> 0x18
          ) * 0x100000001b3;
  lVar1 = *(longlong *)(DAT_147cd2e98 + 8 + uVar2 * 0x10);
  if (lVar1 != DAT_147cd2e88) {
    if ((int)param_1 == *(int *)(lVar1 + 0x10)) goto LAB_1403ed638;
    while (lVar1 != *(longlong *)(DAT_147cd2e98 + uVar2 * 0x10)) {
      lVar1 = *(longlong *)(lVar1 + 8);
      if ((int)param_1 == *(int *)(lVar1 + 0x10)) {
        return CONCAT71((int7)((ulonglong)lVar1 >> 8),lVar1 != 0);
      }
    }
  }
  lVar1 = 0;
LAB_1403ed638:
  return CONCAT71((int7)((ulonglong)lVar1 >> 8),lVar1 != 0);
}
