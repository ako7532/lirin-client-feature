
undefined4 FUN_1408c7020(undefined8 param_1,int param_2,undefined4 *param_3)

{
  undefined4 uVar1;
  longlong lVar2;

  lVar2 = FUN_140ae11c0();
  if (param_2 < lVar2) {
    lVar2 = FUN_140ae0e70(param_1,(longlong)param_2);
    if (lVar2 != 0) {
      uVar1 = FUN_140ad14b0(lVar2);
      *param_3 = uVar1;
      return 1;
    }
  }
  return 0;
}
