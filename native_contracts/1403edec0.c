
undefined1 FUN_1403edec0(longlong param_1,int param_2)

{
  longlong lVar1;
  longlong lVar2;
  int aiStackX_10 [2];

  aiStackX_10[0] = param_2;
  lVar1 = thunk_FUN_1467d1800(*(undefined8 *)(param_1 + 0x4588),*(undefined8 *)(param_1 + 0x4590),
                              param_2);
  if (lVar1 == *(longlong *)(param_1 + 0x4590)) {
    return 0;
  }
  lVar2 = FUN_1405353b0(DAT_147ccab10,param_2);
  if (lVar2 != 0) {
    FUN_1404bf290(lVar2,0);
  }
  FUN_1468725c0(lVar1,lVar1 + 4,*(longlong *)(param_1 + 0x4590) - (lVar1 + 4));
  *(longlong *)(param_1 + 0x4590) = *(longlong *)(param_1 + 0x4590) + -4;
  FUN_140393370(param_1 + 0x45a0,aiStackX_10);
  if (*(int *)(param_1 + 0x433c) == param_2) {
    lVar1 = FUN_1405353b0(DAT_147ccab10,*(undefined4 *)(param_1 + 0xa8));
    if (lVar1 != 0) {
      FUN_1404d33e0(lVar1);
      *(undefined4 *)(param_1 + 0xf8) = 0;
    }
    *(undefined4 *)(param_1 + 0xcc) = 0;
    FUN_1403f42b0(param_1);
    *(undefined4 *)(param_1 + 0xec) = 0;
  }
  FUN_14037fbe0(DAT_147ccaa18,*(undefined1 *)(DAT_147ccaa18 + 0x98));
  FUN_140495ef0(DAT_147ccb198);
  return 1;
}
