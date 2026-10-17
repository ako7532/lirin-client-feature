
void FUN_140401300(undefined8 param_1,undefined8 param_2)

{
  char cVar1;
  undefined1 uVar2;
  undefined4 auStackX_18 [4];

  cVar1 = FUN_1408c7020(param_2,0,auStackX_18);
  if (cVar1 == '\0') {
    FUN_1408c7320(0);
    return;
  }
  uVar2 = FUN_1403edec0(DAT_147ccaf00,auStackX_18[0]);
  FUN_140aa5ea0(&DAT_1468fb3cc,uVar2);
  return;
}
