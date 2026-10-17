
longlong * FUN_140b0d5d0(void)

{
  undefined8 uVar1;
  int iVar2;
  longlong *plVar3;
  longlong *plVar4;
  longlong lVar5;

  plVar3 = (longlong *)FUN_140adb610();
  if (plVar3 == (longlong *)0x0) {
    return (longlong *)0x0;
  }
  if (*(longlong *)(*(longlong *)(DAT_147dfb040 + 8) + 0x10) == 0) {
                    /* WARNING: Subroutine does not return */
    FUN_140af7220("PyImport_GetModuleDict: no module dictionary!");
  }
  uVar1 = *(undefined8 *)(*(longlong *)(DAT_147dfb040 + 8) + 0x10);
  plVar4 = (longlong *)FUN_140ae8fe0(uVar1,plVar3);
  if (plVar4 != (longlong *)0x0) {
    if ((undefined *)plVar4[1] == &DAT_147551e70) goto LAB_140b0d69a;
    iVar2 = FUN_140ab1130();
    if (iVar2 != 0) goto LAB_140b0d69a;
  }
  lVar5 = FUN_140af18d0();
  if (lVar5 == 0) {
    plVar4 = (longlong *)FUN_140b070f0(plVar3 + 4);
    if (plVar4 != (longlong *)0x0) {
      iVar2 = FUN_140ae8c30(uVar1,plVar3,plVar4);
      *plVar4 = *plVar4 + -1;
      if (iVar2 == 0) {
        if (*plVar4 == 0) {
          (**(code **)(plVar4[1] + 0x30))(plVar4);
        }
      }
      else {
        if (*plVar4 == 0) {
          (**(code **)(plVar4[1] + 0x30))(plVar4);
        }
        plVar4 = (longlong *)0x0;
      }
    }
  }
  else {
    plVar4 = (longlong *)0x0;
  }
LAB_140b0d69a:
  *plVar3 = *plVar3 + -1;
  if (*plVar3 == 0) {
    (**(code **)(plVar3[1] + 0x30))(plVar3);
  }
  return plVar4;
}
