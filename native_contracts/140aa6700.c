
longlong * FUN_140aa6700(longlong *param_1,longlong *param_2,uint param_3)

{
  char cVar1;
  short sVar2;
  uint *puVar3;
  short *psVar4;
  undefined4 *puVar5;
  undefined1 *puVar6;
  undefined8 *puVar7;
  size_t *psVar8;
  code *UNRECOVERED_JUMPTABLE;
  undefined8 uVar9;
  short *psVar10;
  undefined4 uVar11;
  uint uVar12;
  longlong *plVar13;
  longlong lVar14;
  size_t sVar15;
  undefined *puVar16;
  char *pcVar17;
  uint uVar18;
  longlong *plVar19;
  int iVar20;
  undefined1 auStackX_8 [8];
  undefined4 uStack_38;
  undefined4 uStack_34;
  undefined4 uStack_30;
  undefined4 uStack_2c;

  cVar1 = *(char *)*param_1;
  pcVar17 = (char *)*param_1 + 1;
  *param_1 = (longlong)pcVar17;
joined_r0x000140aa6729:
  if (0x72 < (int)cVar1 - 9U) {
switchD_140aa6747_caseD_1:
    pcVar17 = "bad format char passed to Py_BuildValue";
    puVar16 = PTR_DAT_147556318;
LAB_140aa676b:
    FUN_140af20e0(puVar16,pcVar17);
    return (longlong *)0x0;
  }
  switch((int)cVar1 - 9U) {
  case 0:
  case 0x17:
  case 0x23:
  case 0x31:
    goto switchD_140aa6747_caseD_0;
  default:
    goto switchD_140aa6747_caseD_1;
  case 0x1f:
    uVar11 = FUN_140aa6180(pcVar17,0x29);
    plVar13 = (longlong *)FUN_140aa65f0(param_1,param_2,0x29,uVar11,param_3);
    return plVar13;
  case 0x39:
  case 0x3f:
  case 0x59:
  case 0x5f:
  case 0x60:
  case 99:
    puVar3 = (uint *)*param_2;
    *param_2 = (longlong)(puVar3 + 2);
    uVar18 = *puVar3;
    break;
  case 0x3b:
    plVar13 = (longlong *)*param_2;
    *param_2 = (longlong)(plVar13 + 1);
    puVar5 = (undefined4 *)*plVar13;
    uStack_38 = *puVar5;
    uStack_34 = puVar5[1];
    uStack_30 = puVar5[2];
    uStack_2c = puVar5[3];
    plVar13 = (longlong *)FUN_140b268d0(&uStack_38);
    return plVar13;
  case 0x40:
  case 0x62:
    puVar3 = (uint *)*param_2;
    *param_2 = (longlong)(puVar3 + 2);
    uVar18 = *puVar3;
    uVar12 = FUN_140ace460();
    if (uVar12 < uVar18) {
      plVar13 = (longlong *)FUN_140ad2320(uVar18);
      return plVar13;
    }
    break;
  case 0x42:
    puVar7 = (undefined8 *)*param_2;
    *param_2 = (longlong)(puVar7 + 1);
    plVar13 = (longlong *)FUN_140ad2390(*puVar7);
    return plVar13;
  case 0x43:
    puVar7 = (undefined8 *)*param_2;
    *param_2 = (longlong)(puVar7 + 1);
    plVar13 = (longlong *)FUN_140ad1be0(*puVar7);
    return plVar13;
  case 0x45:
  case 0x46:
  case 0x4a:
    puVar7 = (undefined8 *)*param_2;
    cVar1 = *pcVar17;
    *param_2 = (longlong)(puVar7 + 1);
    if (cVar1 == '&') {
      UNRECOVERED_JUMPTABLE = (code *)*puVar7;
      *param_2 = (longlong)(puVar7 + 2);
      uVar9 = puVar7[1];
      *param_1 = *param_1 + 1;
                    /* WARNING: Could not recover jumptable at 0x000140aa6b36. Too many branches */
                    /* WARNING: Treating indirect jump as call */
      plVar13 = (longlong *)(*UNRECOVERED_JUMPTABLE)(uVar9,UNRECOVERED_JUMPTABLE);
      return plVar13;
    }
    plVar13 = (longlong *)*puVar7;
    if (plVar13 == (longlong *)0x0) {
      lVar14 = FUN_140af18d0();
      if (lVar14 == 0) {
        FUN_140af20e0(PTR_DAT_147556318,"NULL object passed to Py_BuildValue");
      }
    }
    else if (*(char *)(*param_1 + -1) != 'N') {
      *plVar13 = *plVar13 + 1;
      return plVar13;
    }
    return plVar13;
  case 0x52:
    iVar20 = FUN_140aa6180(pcVar17,0x5d);
    if (iVar20 < 0) {
      return (longlong *)0x0;
    }
    plVar13 = (longlong *)FUN_140ae41e0((longlong)iVar20);
    if (plVar13 == (longlong *)0x0) {
      FUN_140aa62a0(param_1,param_2,0x5d,iVar20,param_3);
      return (longlong *)0x0;
    }
    plVar19 = (longlong *)0x0;
    if (0 < iVar20) {
      do {
        lVar14 = FUN_140aa6700(param_1,param_2,param_3);
        if (lVar14 == 0) {
          FUN_140aa62a0(param_1,param_2,0x5d,(iVar20 - (int)plVar19) + -1,param_3);
          *plVar13 = *plVar13 + -1;
          if (*plVar13 != 0) {
            return (longlong *)0x0;
          }
          (**(code **)(plVar13[1] + 0x30))(plVar13);
          return (longlong *)0x0;
        }
        uVar18 = (int)plVar19 + 1;
        *(longlong *)(plVar13[3] + (longlong)plVar19 * 8) = lVar14;
        plVar19 = (longlong *)(ulonglong)uVar18;
      } while ((int)uVar18 < iVar20);
    }
    if (*(char *)*param_1 == ']') {
      *param_1 = (longlong)((char *)*param_1 + 1);
    }
    else {
      *plVar13 = *plVar13 + -1;
      if (*plVar13 == 0) {
        (**(code **)(plVar13[1] + 0x30))(plVar13);
      }
      FUN_140af20e0(PTR_DAT_147556318,"Unmatched paren in format");
      plVar13 = (longlong *)0x0;
    }
    return plVar13;
  case 0x5a:
    puVar6 = (undefined1 *)*param_2;
    *param_2 = (longlong)(puVar6 + 8);
    auStackX_8[0] = *puVar6;
    plVar13 = (longlong *)FUN_140adb780(auStackX_8,1);
    return plVar13;
  case 0x5b:
  case 0x5d:
    puVar7 = (undefined8 *)*param_2;
    *param_2 = (longlong)(puVar7 + 1);
    plVar13 = (longlong *)FUN_140b14a50((int)*puVar7);
    return plVar13;
  case 0x65:
    puVar7 = (undefined8 *)*param_2;
    *param_2 = (longlong)(puVar7 + 1);
    plVar13 = (longlong *)FUN_140ace1e0(*puVar7);
    return plVar13;
  case 0x6a:
  case 0x71:
    puVar7 = (undefined8 *)*param_2;
    *param_2 = (longlong)(puVar7 + 1);
    pcVar17 = (char *)*puVar7;
    if (*(char *)*param_1 == '#') {
      *param_1 = (longlong)((char *)*param_1 + 1);
      psVar8 = (size_t *)*param_2;
      *param_2 = (longlong)(psVar8 + 1);
      if ((param_3 & 1) == 0) {
        sVar15 = (size_t)(int)*psVar8;
      }
      else {
        sVar15 = *psVar8;
      }
    }
    else {
      sVar15 = 0xffffffffffffffff;
    }
    if (pcVar17 == (char *)0x0) goto LAB_140aa69c9;
    if ((-1 < (longlong)sVar15) || (sVar15 = strlen(pcVar17), sVar15 < 0x8000000000000000)) {
      plVar13 = (longlong *)FUN_140adb780(pcVar17,sVar15);
      return plVar13;
    }
    pcVar17 = "string too long for Python string";
    puVar16 = PTR_DAT_147555828;
    goto LAB_140aa676b;
  case 0x6c:
    puVar7 = (undefined8 *)*param_2;
    *param_2 = (longlong)(puVar7 + 1);
    psVar4 = (short *)*puVar7;
    if (*(char *)*param_1 == '#') {
      *param_1 = (longlong)((char *)*param_1 + 1);
      plVar13 = (longlong *)*param_2;
      *param_2 = (longlong)(plVar13 + 1);
      if ((param_3 & 1) == 0) {
        lVar14 = (longlong)(int)*plVar13;
      }
      else {
        lVar14 = *plVar13;
      }
    }
    else {
      lVar14 = -1;
    }
    if (psVar4 != (short *)0x0) {
      if (lVar14 < 0) {
        iVar20 = 0;
        sVar2 = *psVar4;
        psVar10 = psVar4;
        while (sVar2 != 0) {
          iVar20 = iVar20 + 1;
          psVar10 = psVar10 + 1;
          sVar2 = *psVar10;
        }
        lVar14 = (longlong)iVar20;
      }
      plVar13 = (longlong *)FUN_140ac3880(psVar4,lVar14);
      return plVar13;
    }
LAB_140aa69c9:
    DAT_1475437d8 = DAT_1475437d8 + 1;
    return &DAT_1475437d8;
  case 0x72:
    uVar11 = FUN_140aa6180(pcVar17,0x7d);
    plVar13 = (longlong *)FUN_140aa6430(param_1,param_2,0x7d,uVar11,param_3);
    return plVar13;
  }
  plVar13 = (longlong *)FUN_140ace140(uVar18);
  return plVar13;
switchD_140aa6747_caseD_0:
  cVar1 = *pcVar17;
  pcVar17 = pcVar17 + 1;
  *param_1 = (longlong)pcVar17;
  goto joined_r0x000140aa6729;
}
