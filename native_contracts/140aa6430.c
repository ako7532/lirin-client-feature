
longlong *
FUN_140aa6430(longlong *param_1,undefined8 param_2,int param_3,uint param_4,undefined4 param_5)

{
  int iVar1;
  longlong *plVar2;
  longlong *plVar3;
  longlong *plVar4;
  int iVar5;

  if (-1 < (int)param_4) {
    if ((param_4 & 1) == 0) {
      plVar2 = (longlong *)FUN_140ae8ae0();
      if (plVar2 != (longlong *)0x0) {
        iVar5 = 0;
        if (0 < (int)param_4) {
          do {
            plVar3 = (longlong *)FUN_140aa6700(param_1,param_2,param_5);
            if (plVar3 == (longlong *)0x0) {
              FUN_140aa62a0(param_1,param_2,param_3,(param_4 - iVar5) + -1,param_5);
LAB_140aa6598:
              *plVar2 = *plVar2 + -1;
              if (*plVar2 != 0) {
                return (longlong *)0x0;
              }
              (**(code **)(plVar2[1] + 0x30))(plVar2);
              return (longlong *)0x0;
            }
            plVar4 = (longlong *)FUN_140aa6700(param_1,param_2,param_5);
            if ((plVar4 == (longlong *)0x0) ||
               (iVar1 = FUN_140ae8c30(plVar2,plVar3,plVar4), iVar1 < 0)) {
              FUN_140aa62a0(param_1,param_2,param_3,(param_4 - iVar5) + -2,param_5);
              *plVar3 = *plVar3 + -1;
              if (*plVar3 == 0) {
                (**(code **)(plVar3[1] + 0x30))(plVar3);
              }
              if ((plVar4 != (longlong *)0x0) && (*plVar4 = *plVar4 + -1, *plVar4 == 0)) {
                (**(code **)(plVar4[1] + 0x30))(plVar4);
              }
              goto LAB_140aa6598;
            }
            *plVar3 = *plVar3 + -1;
            if (*plVar3 == 0) {
              (**(code **)(plVar3[1] + 0x30))(plVar3);
            }
            *plVar4 = *plVar4 + -1;
            if (*plVar4 == 0) {
              (**(code **)(plVar4[1] + 0x30))(plVar4);
            }
            iVar5 = iVar5 + 2;
          } while (iVar5 < (int)param_4);
        }
        if (*(char *)*param_1 != param_3) {
          *plVar2 = *plVar2 + -1;
          if (*plVar2 == 0) {
            (**(code **)(plVar2[1] + 0x30))(plVar2);
          }
          FUN_140af20e0(PTR_DAT_147556318,"Unmatched paren in format");
          return (longlong *)0x0;
        }
        if (param_3 != 0) {
          *param_1 = (longlong)((char *)*param_1 + 1);
          return plVar2;
        }
        return plVar2;
      }
    }
    else {
      FUN_140af20e0(PTR_DAT_147556318,"Bad dict format");
    }
    FUN_140aa62a0(param_1,param_2,param_3,param_4,param_5);
  }
  return (longlong *)0x0;
}
