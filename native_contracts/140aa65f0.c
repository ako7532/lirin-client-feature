
longlong *
FUN_140aa65f0(longlong *param_1,undefined8 param_2,int param_3,int param_4,undefined4 param_5)

{
  longlong *plVar1;
  longlong lVar2;
  uint uVar3;
  ulonglong uVar4;

  if (-1 < param_4) {
    plVar1 = (longlong *)FUN_140ae0f10((longlong)param_4);
    if (plVar1 == (longlong *)0x0) {
      FUN_140aa62a0(param_1,param_2,param_3,param_4,param_5);
    }
    else {
      uVar4 = 0;
      if (0 < param_4) {
        do {
          lVar2 = FUN_140aa6700(param_1,param_2,param_5);
          if (lVar2 == 0) {
            FUN_140aa62a0(param_1,param_2,param_3,(param_4 - (int)uVar4) + -1,param_5);
            *plVar1 = *plVar1 + -1;
            if (*plVar1 != 0) {
              return (longlong *)0x0;
            }
            (**(code **)(plVar1[1] + 0x30))(plVar1);
            return (longlong *)0x0;
          }
          plVar1[uVar4 + 3] = lVar2;
          uVar3 = (int)uVar4 + 1;
          uVar4 = (ulonglong)uVar3;
        } while ((int)uVar3 < param_4);
      }
      if (*(char *)*param_1 == param_3) {
        if (param_3 != 0) {
          *param_1 = (longlong)((char *)*param_1 + 1);
        }
        return plVar1;
      }
      *plVar1 = *plVar1 + -1;
      if (*plVar1 == 0) {
        (**(code **)(plVar1[1] + 0x30))(plVar1);
      }
      FUN_140af20e0(PTR_DAT_147556318,"Unmatched paren in format");
    }
  }
  return (longlong *)0x0;
}
