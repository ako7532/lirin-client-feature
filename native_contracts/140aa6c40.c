
undefined8 * FUN_140aa6c40(undefined8 param_1,undefined8 param_2,undefined4 param_3)

{
  int iVar1;
  undefined8 *puVar2;
  undefined8 uStackX_8;
  undefined8 uStackX_10;

  uStackX_10 = param_1;
  iVar1 = FUN_140aa6180(param_1,0);
  if (iVar1 < 0) {
    return (undefined8 *)0x0;
  }
  if (iVar1 == 0) {
    DAT_1475437d8 = DAT_1475437d8 + 1;
    return &DAT_1475437d8;
  }
  uStackX_8 = param_2;
  if (iVar1 == 1) {
    puVar2 = (undefined8 *)FUN_140aa6700(&uStackX_10,&uStackX_8,param_3);
    return puVar2;
  }
  puVar2 = (undefined8 *)FUN_140aa65f0(&uStackX_10,&uStackX_8,0,iVar1,param_3);
  return puVar2;
}
