
FUNCTION chr.GetVIDInfo 14052ac40

/* WARNING: Function: __security_check_cookie replaced with injection: security_check_cookie */

void FUN_14052ac40(undefined8 param_1,undefined8 param_2)

{
  char cVar1;
  longlong lVar2;
  uint uVar3;
  char cVar4;
  uint uVar5;
  longlong *plVar6;
  longlong *plVar7;
  longlong *plVar8;
  longlong *plVar9;
  longlong *plVar10;
  undefined1 auStack_578 [32];
  undefined4 uStack_558;
  undefined4 uStack_550;
  undefined1 *puStack_548;
  uint uStack_538;
  int iStack_534;
  int aiStack_530 [2];
  float fStack_528;
  float fStack_524;
  undefined1 uStack_518;
  undefined1 auStack_517 [255];
  undefined1 auStack_418 [1024];
  ulonglong uStack_18;
  
  uStack_18 = DAT_147a4e640 ^ (ulonglong)auStack_578;
  cVar4 = FUN_140897b40(param_2,0,&uStack_538);
  lVar2 = DAT_147a6b450;
  if (cVar4 == '\0') {
    FUN_140897e30();
    return;
  }
  uStack_518 = 0;
  FUN_14665df90(auStack_517,0,0xff);
  plVar10 = *(longlong **)(lVar2 + 0xf8);
  plVar6 = (longlong *)plVar10[1];
  cVar4 = *(char *)((longlong)plVar6 + 0x19);
  plVar7 = plVar10;
  while (cVar4 == '\0') {
    plVar8 = plVar6;
    if (*(uint *)(plVar6 + 4) < uStack_538) {
      plVar6 = plVar6 + 2;
      plVar8 = plVar7;
    }
    plVar6 = (longlong *)*plVar6;
    plVar7 = plVar8;
    cVar4 = *(char *)((longlong)plVar6 + 0x19);
  }
  if ((((*(char *)((longlong)plVar7 + 0x19) == '\0') && (*(uint *)(plVar7 + 4) <= uStack_538)) &&
      (plVar10 != plVar7)) && (plVar7[5] != 0)) {
    FUN_1404a2ec0(plVar7[5],&fStack_528);
    aiStack_530[0] = (int)fStack_528;
    iStack_534 = (int)fStack_524;
    FUN_1404f80f0(DAT_147a6b4f0,aiStack_530,&iStack_534);
    FUN_140253190(&uStack_518,&DAT_146707390,aiStack_530[0],iStack_534);
  }
  uVar3 = uStack_538;
  plVar10 = (longlong *)**(longlong **)(lVar2 + 0x120);
  if (plVar10 != *(longlong **)(lVar2 + 0x120)) {
    do {
      uVar5 = FUN_14049f0a0(plVar10[2]);
      if (uVar5 == uVar3) {
        uStack_550 = 1;
        goto LAB_14052ad97;
      }
      plVar10 = (longlong *)*plVar10;
    } while (plVar10 != (longlong *)*(longlong *)(lVar2 + 0x120));
  }
  uStack_550 = 0;
LAB_14052ad97:
  plVar10 = *(longlong **)(lVar2 + 0xf8);
  plVar7 = (longlong *)plVar10[1];
  cVar1 = *(char *)((longlong)plVar7 + 0x19);
  plVar8 = plVar10;
  plVar6 = plVar7;
  cVar4 = cVar1;
  while (cVar4 == '\0') {
    plVar9 = plVar6;
    if (*(uint *)(plVar6 + 4) < uStack_538) {
      plVar6 = plVar6 + 2;
      plVar9 = plVar8;
    }
    plVar6 = (longlong *)*plVar6;
    plVar8 = plVar9;
    cVar4 = *(char *)((longlong)plVar6 + 0x19);
  }
  plVar6 = plVar10;
  if ((*(char *)((longlong)plVar8 + 0x19) != '\0') ||
     (uStack_558 = 1, uStack_538 < *(uint *)(plVar8 + 4))) {
    uStack_558 = 0;
  }
  while (cVar1 == '\0') {
    plVar8 = plVar7;
    if (*(uint *)(plVar7 + 4) < uStack_538) {
      plVar7 = plVar7 + 2;
      plVar8 = plVar6;
    }
    plVar7 = (longlong *)*plVar7;
    plVar6 = plVar8;
    cVar1 = *(char *)((longlong)plVar7 + 0x19);
  }
  if ((*(char *)((longlong)plVar6 + 0x19) != '\0') || (uStack_538 < *(uint *)(plVar6 + 4))) {
    plVar6 = plVar10;
  }
  puStack_548 = &uStack_518;
  FUN_140253190(auStack_418,&DAT_1467073a0,uStack_538,plVar10 != plVar6);
  FUN_140a6b650(&DAT_1466e2188,auStack_418);
  return;
}



FUNCTION chr.FindVIDByRace 14052a890

void FUN_14052a890(undefined8 param_1,undefined8 param_2)

{
  longlong lVar1;
  longlong *plVar2;
  longlong lVar3;
  longlong *plVar4;
  char cVar5;
  int iVar6;
  undefined4 uVar7;
  longlong *plVar8;
  int aiStackX_18 [4];
  
  cVar5 = FUN_140897b40(param_2,0,aiStackX_18);
  lVar3 = DAT_147a6b450;
  if (cVar5 == '\0') {
    FUN_140897e40(0);
    return;
  }
  plVar8 = (longlong *)**(longlong **)(DAT_147a6b450 + 0xf8);
  if (plVar8 != *(longlong **)(DAT_147a6b450 + 0xf8)) {
    do {
      lVar1 = plVar8[5];
      if (((lVar1 != 0) && (iVar6 = FUN_14049ff40(lVar1), iVar6 == 0)) &&
         (iVar6 = FUN_14049f060(lVar1), iVar6 == aiStackX_18[0])) {
        uVar7 = FUN_14049f0a0(lVar1);
        FUN_140a6b650(&DAT_1466e218c,uVar7);
        return;
      }
      plVar2 = (longlong *)plVar8[2];
      if (*(char *)((longlong)plVar2 + 0x19) == '\0') {
        cVar5 = *(char *)(*plVar2 + 0x19);
        plVar8 = plVar2;
        while (cVar5 == '\0') {
          plVar8 = (longlong *)*plVar8;
          cVar5 = *(char *)(*plVar8 + 0x19);
        }
      }
      else {
        cVar5 = *(char *)(plVar8[1] + 0x19);
        plVar4 = (longlong *)plVar8[1];
        plVar2 = plVar8;
        while ((plVar8 = plVar4, cVar5 == '\0' && (plVar2 == (longlong *)plVar8[2]))) {
          cVar5 = *(char *)(plVar8[1] + 0x19);
          plVar4 = (longlong *)plVar8[1];
          plVar2 = plVar8;
        }
      }
    } while (plVar8 != *(longlong **)(lVar3 + 0xf8));
  }
  FUN_140a6b650(&DAT_1466e218c,0);
  return;
}



FUNCTION chr.GetNearestResourceVID 14052aab0

void FUN_14052aab0(undefined8 param_1,undefined8 param_2)

{
  longlong lVar1;
  longlong *plVar2;
  longlong *plVar3;
  char cVar4;
  int iVar5;
  undefined4 uVar6;
  longlong *plVar7;
  longlong lVar8;
  float fVar9;
  float fVar10;
  float afStackX_18 [4];
  float fStack_38;
  float fStack_34;
  float fStack_28;
  float fStack_24;
  
  cVar4 = FUN_140897a60(param_2,0,afStackX_18);
  lVar1 = DAT_147a6b450;
  if (cVar4 == '\0') {
    afStackX_18[0] = DAT_1466f6ca0;
  }
  fVar10 = afStackX_18[0];
  if (*(longlong *)(DAT_147a6b450 + 0xd8) == 0) {
    FUN_140a6b650(&DAT_1466e218c,0);
    return;
  }
  FUN_1404a2ec0(*(longlong *)(DAT_147a6b450 + 0xd8),&fStack_38);
  lVar8 = 0;
  plVar7 = (longlong *)**(longlong **)(lVar1 + 0xf8);
  if (*(char *)((longlong)plVar7 + 0x19) == '\0') {
    do {
      lVar1 = plVar7[5];
      iVar5 = FUN_1404a0840(lVar1);
      if (iVar5 != 0) {
        FUN_1404a2ec0(lVar1,&fStack_28);
        fVar9 = SQRT((fStack_34 - fStack_24) * (fStack_34 - fStack_24) +
                     (fStack_38 - fStack_28) * (fStack_38 - fStack_28));
        if (fVar9 < fVar10) {
          lVar8 = lVar1;
          fVar10 = fVar9;
        }
      }
      plVar2 = (longlong *)plVar7[2];
      if (*(char *)((longlong)plVar2 + 0x19) == '\0') {
        cVar4 = *(char *)(*plVar2 + 0x19);
        plVar7 = plVar2;
        while (cVar4 == '\0') {
          plVar7 = (longlong *)*plVar7;
          cVar4 = *(char *)(*plVar7 + 0x19);
        }
      }
      else {
        cVar4 = *(char *)(plVar7[1] + 0x19);
        plVar3 = (longlong *)plVar7[1];
        plVar2 = plVar7;
        while ((plVar7 = plVar3, cVar4 == '\0' && (plVar2 == (longlong *)plVar7[2]))) {
          cVar4 = *(char *)(plVar7[1] + 0x19);
          plVar3 = (longlong *)plVar7[1];
          plVar2 = plVar7;
        }
      }
    } while (*(char *)((longlong)plVar7 + 0x19) == '\0');
    if (lVar8 != 0) {
      uVar6 = FUN_14049f0a0(lVar8);
      FUN_140a6b650(&DAT_1466e218c,uVar6);
      return;
    }
  }
  FUN_140a6b650(&DAT_1466e218c,0);
  return;
}



FUNCTION chr.GetPixelPosition 1405289d0

void FUN_1405289d0(undefined8 param_1,undefined8 param_2)

{
  longlong *plVar1;
  longlong *plVar2;
  char cVar3;
  longlong *plVar4;
  longlong *plVar5;
  uint auStackX_18 [4];
  float fStack_18;
  float fStack_14;
  float fStack_10;
  
  cVar3 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar3 != '\0') {
    plVar1 = *(longlong **)(DAT_147a6b450 + 0xf8);
    plVar4 = (longlong *)plVar1[1];
    cVar3 = *(char *)((longlong)plVar4 + 0x19);
    plVar2 = plVar1;
    while (cVar3 == '\0') {
      plVar5 = plVar4;
      if (*(uint *)(plVar4 + 4) < auStackX_18[0]) {
        plVar4 = plVar4 + 2;
        plVar5 = plVar2;
      }
      plVar4 = (longlong *)*plVar4;
      plVar2 = plVar5;
      cVar3 = *(char *)((longlong)plVar4 + 0x19);
    }
    if ((((*(char *)((longlong)plVar2 + 0x19) == '\0') && (*(uint *)(plVar2 + 4) <= auStackX_18[0]))
        && (plVar1 != plVar2)) && (plVar2[5] != 0)) {
      FUN_1404a2ec0(plVar2[5],&fStack_18);
      FUN_140a6b650(&DAT_1466f237c,(double)fStack_18,(double)fStack_14,(double)fStack_10);
      return;
    }
  }
  FUN_140897e40(0);
  return;
}



FUNCTION chr.GetInstanceType 140528830

void FUN_140528830(undefined8 param_1,undefined8 param_2)

{
  longlong *plVar1;
  longlong *plVar2;
  char cVar3;
  undefined4 uVar4;
  longlong *plVar5;
  longlong *plVar6;
  uint auStackX_18 [4];
  
  cVar3 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar3 == '\0') {
    FUN_140897e40(0);
    return;
  }
  plVar1 = *(longlong **)(DAT_147a6b450 + 0xf8);
  plVar5 = (longlong *)plVar1[1];
  cVar3 = *(char *)((longlong)plVar5 + 0x19);
  plVar2 = plVar1;
  while (cVar3 == '\0') {
    plVar6 = plVar5;
    if (*(uint *)(plVar5 + 4) < auStackX_18[0]) {
      plVar5 = plVar5 + 2;
      plVar6 = plVar2;
    }
    plVar5 = (longlong *)*plVar5;
    plVar2 = plVar6;
    cVar3 = *(char *)((longlong)plVar5 + 0x19);
  }
  if ((((*(char *)((longlong)plVar2 + 0x19) == '\0') && (*(uint *)(plVar2 + 4) <= auStackX_18[0]))
      && (plVar1 != plVar2)) && (plVar2[5] != 0)) {
    uVar4 = FUN_14049e380();
    FUN_140a6b650(&DAT_1466e218c,uVar4);
    return;
  }
  FUN_140a6b650(&DAT_1466e218c,6);
  return;
}



FUNCTION chr.GetNameByVID 140528920

void FUN_140528920(undefined8 param_1,undefined8 param_2)

{
  longlong *plVar1;
  longlong *plVar2;
  char cVar3;
  longlong *plVar4;
  undefined8 uVar5;
  longlong *plVar6;
  uint auStackX_18 [4];
  
  cVar3 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar3 == '\0') {
    FUN_140897e40(0);
    return;
  }
  plVar1 = *(longlong **)(DAT_147a6b450 + 0xf8);
  plVar4 = (longlong *)plVar1[1];
  cVar3 = *(char *)((longlong)plVar4 + 0x19);
  plVar2 = plVar1;
  while (cVar3 == '\0') {
    plVar6 = plVar4;
    if (*(uint *)(plVar4 + 4) < auStackX_18[0]) {
      plVar4 = plVar4 + 2;
      plVar6 = plVar2;
    }
    plVar4 = (longlong *)*plVar4;
    plVar2 = plVar6;
    cVar3 = *(char *)((longlong)plVar4 + 0x19);
  }
  if ((((*(char *)((longlong)plVar2 + 0x19) == '\0') && (*(uint *)(plVar2 + 4) <= auStackX_18[0]))
      && (plVar1 != plVar2)) && (plVar2[5] != 0)) {
    uVar5 = FUN_14049eb40();
    FUN_140a6b650(&DAT_1466e2188,uVar5);
    return;
  }
  FUN_140a6b650(&DAT_1466e2188,&DAT_1466f8ef4);
  return;
}



FUNCTION chr.GetVirtualNumber 140528c80

void FUN_140528c80(undefined8 param_1,undefined8 param_2)

{
  longlong *plVar1;
  longlong *plVar2;
  char cVar3;
  undefined4 uVar4;
  longlong *plVar5;
  longlong *plVar6;
  uint auStackX_18 [4];
  
  cVar3 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar3 == '\0') {
    FUN_140897e40(0);
    return;
  }
  plVar1 = *(longlong **)(DAT_147a6b450 + 0xf8);
  plVar5 = (longlong *)plVar1[1];
  cVar3 = *(char *)((longlong)plVar5 + 0x19);
  plVar2 = plVar1;
  while (cVar3 == '\0') {
    plVar6 = plVar5;
    if (*(uint *)(plVar5 + 4) < auStackX_18[0]) {
      plVar5 = plVar5 + 2;
      plVar6 = plVar2;
    }
    plVar5 = (longlong *)*plVar5;
    plVar2 = plVar6;
    cVar3 = *(char *)((longlong)plVar5 + 0x19);
  }
  if ((((*(char *)((longlong)plVar2 + 0x19) == '\0') && (*(uint *)(plVar2 + 4) <= auStackX_18[0]))
      && (plVar1 != plVar2)) && (plVar2[5] != 0)) {
    uVar4 = FUN_14049f0c0();
    FUN_140a6b650(&DAT_1466e218c,uVar4);
    return;
  }
  FUN_140a6b650(&DAT_1466e218c,6);
  return;
}



FUNCTION nonplayer.GetRaceNumByVID 1403dae00

void FUN_1403dae00(undefined8 param_1,undefined8 param_2)

{
  undefined8 uVar1;
  char cVar2;
  undefined4 uVar3;
  longlong lVar4;
  undefined4 *puVar5;
  undefined4 auStackX_18 [4];
  
  cVar2 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar2 == '\0') {
    FUN_140897e40(0);
    return;
  }
  lVar4 = FUN_1405166a0(DAT_147a6b450,auStackX_18[0]);
  uVar1 = DAT_147a6b350;
  if (lVar4 == 0) {
    FUN_140a6b650(&DAT_1466e218c,0xffffffff);
    return;
  }
  uVar3 = FUN_14049f0c0(lVar4);
  puVar5 = (undefined4 *)FUN_1403d0380(uVar1,uVar3);
  uVar3 = 0xffffffff;
  if (puVar5 != (undefined4 *)0x0) {
    uVar3 = *puVar5;
  }
  FUN_140a6b650(&DAT_1466e218c,uVar3);
  return;
}



FUNCTION nonplayer.IsMonsterStone 1403daf50

void FUN_1403daf50(undefined8 param_1,undefined8 param_2)

{
  char cVar1;
  longlong lVar2;
  undefined4 auStackX_18 [4];
  
  cVar1 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar1 == '\0') {
    FUN_140897e40(0);
    return;
  }
  lVar2 = FUN_1403d0380(DAT_147a6b350,auStackX_18[0]);
  if ((lVar2 != 0) && (*(char *)(lVar2 + 0x48) == '\x02')) {
    FUN_140a6b650(&DAT_1466e218c,1);
    return;
  }
  FUN_140a6b650(&DAT_1466e218c,0);
  return;
}



FUNCTION player.GetMainCharacterPosition 1403f4290

void FUN_1403f4290(void)

{
  float fStack_18;
  float fStack_14;
  float fStack_10;
  
  FUN_1403d1d50(DAT_147a6b6b0,&fStack_18);
  FUN_140a6b650(&DAT_1466f237c,(double)fStack_18,(double)fStack_14,(double)fStack_10);
  return;
}



FUNCTION player.GetProjectPosition 1403fa410

void FUN_1403fa410(undefined8 param_1,undefined8 param_2)

{
  undefined4 uVar1;
  undefined4 uVar2;
  float fVar3;
  undefined8 uVar4;
  char cVar5;
  longlong lVar6;
  undefined4 *puVar7;
  int iVar8;
  int iVar9;
  undefined4 auStackX_18 [2];
  int aiStackX_20 [2];
  float fStack_48;
  float fStack_44;
  float afStack_40 [14];
  
  cVar5 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar5 == '\0') {
LAB_1403fa432:
    FUN_140897e40(0);
    return;
  }
  cVar5 = FUN_140897b40(param_2,1,aiStackX_20);
  if (cVar5 == '\0') goto LAB_1403fa432;
  lVar6 = FUN_1403e2dc0(DAT_147a6b8e8,auStackX_18[0]);
  if ((lVar6 != 0) && (*(longlong *)(lVar6 + 0x30) != 0)) {
    puVar7 = (undefined4 *)FUN_140218c30();
    uVar4 = DAT_147a6b678;
    uVar1 = *puVar7;
    uVar2 = puVar7[1];
    fVar3 = (float)puVar7[2];
    FUN_14061ca10();
    FUN_14061e430(uVar4,uVar1,uVar2,(float)aiStackX_20[0] + fVar3,afStack_40,&fStack_44,&fStack_48);
    if ((int)fStack_48 != 1) {
      iVar9 = (int)fStack_44;
      iVar8 = (int)afStack_40[0];
      goto LAB_1403fa522;
    }
  }
  iVar8 = -100;
  iVar9 = -100;
LAB_1403fa522:
  FUN_140a6b650(&DAT_1466e2194,iVar8,iVar9);
  return;
}



FUNCTION effect.CreateEffect 14055d8a0

void FUN_14055d8a0(undefined8 param_1,undefined8 param_2)

{
  undefined8 uVar1;
  char cVar2;
  undefined4 uVar3;
  undefined8 auStackX_18 [2];
  undefined8 uStack_28;
  undefined4 uStack_20;
  undefined1 auStack_18 [24];
  
  cVar2 = FUN_140897c70(param_2,0,auStackX_18);
  if (cVar2 == '\0') {
    FUN_140897e40(0);
    return;
  }
  uVar1 = FUN_140517750(DAT_147a6b450);
  FUN_1404a2ec0(uVar1,auStack_18);
  uStack_28 = 0;
  uStack_20 = 0;
  uVar3 = FUN_14057e950(DAT_147a6b698,auStackX_18[0],auStack_18,&uStack_28,DAT_1466e0f04);
  FUN_140a6b650(&DAT_1466e218c,uVar3);
  return;
}



FUNCTION effect.CreateEffectAtPosition 14055db60

void FUN_14055db60(undefined8 param_1,undefined8 param_2)

{
  float fVar1;
  char cVar2;
  undefined4 uVar3;
  longlong lVar4;
  float afStackX_18 [2];
  undefined4 auStackX_20 [2];
  float fStack_58;
  float fStack_54;
  float fStack_50;
  float fStack_4c;
  undefined8 uStack_48;
  undefined8 uStack_40;
  undefined4 uStack_38;
  float fStack_34;
  float fStack_30;
  float fStack_2c;
  float fStack_28;
  float fStack_24;
  float fStack_20;
  
  cVar2 = FUN_140897c70(param_2,0,&uStack_48);
  if (cVar2 != '\0') {
    cVar2 = FUN_140897a60(param_2,1,&fStack_54);
    if (cVar2 != '\0') {
      cVar2 = FUN_140897a60(param_2,2,&fStack_50);
      if (cVar2 != '\0') {
        cVar2 = FUN_140897a60(param_2,3,&fStack_4c);
        if (cVar2 != '\0') {
          auStackX_20[0] = 0;
          lVar4 = FUN_140a9f870(param_2);
          if (4 < lVar4) {
            FUN_140897a60(param_2,4,auStackX_20);
          }
          fVar1 = DAT_1466e0f04;
          afStackX_18[0] = 1.0;
          lVar4 = FUN_140a9f870(param_2);
          if (5 < lVar4) {
            FUN_140897a60(param_2,5,afStackX_18);
          }
          fStack_58 = afStackX_18[0];
          lVar4 = FUN_140a9f870(param_2);
          if (6 < lVar4) {
            FUN_140897a60(param_2,6,&fStack_58);
          }
          if ((afStackX_18[0] == fVar1) && (fStack_58 == fVar1)) {
            uStack_38 = auStackX_20[0];
            fStack_34 = fStack_54;
            fStack_30 = fStack_50;
            fStack_2c = fStack_4c;
            uStack_40 = 0;
            uVar3 = FUN_14057e950(DAT_147a6b698,uStack_48,&fStack_34,&uStack_40,fVar1);
          }
          else {
            fStack_2c = fStack_58;
            uStack_38 = auStackX_20[0];
            fStack_28 = fStack_54;
            fStack_24 = fStack_50;
            fStack_34 = afStackX_18[0];
            fStack_30 = afStackX_18[0];
            fStack_20 = fStack_4c;
            uStack_40 = 0;
            uVar3 = FUN_14057f090(DAT_147a6b698,uStack_48,&fStack_28,&uStack_40,afStackX_18[0],
                                  &fStack_34);
          }
          FUN_140a6b650(&DAT_1466e218c,uVar3);
          return;
        }
      }
    }
  }
  FUN_140897e40(0);
  return;
}



FUNCTION effect.UpdateScaledEffect 14055e1b0

void FUN_14055e1b0(undefined8 param_1,undefined8 param_2)

{
  char cVar1;
  undefined1 uVar2;
  longlong lVar3;
  undefined4 auStackX_18 [2];
  undefined4 auStackX_20 [2];
  undefined4 uStack_48;
  undefined4 uStack_44;
  undefined4 uStack_40;
  undefined4 uStack_3c;
  undefined4 uStack_38;
  undefined4 uStack_34;
  undefined4 uStack_30;
  undefined4 uStack_2c;
  undefined8 uStack_28;
  undefined4 uStack_20;
  undefined4 uStack_1c;
  undefined4 uStack_18;
  undefined4 uStack_14;
  
  cVar1 = FUN_140897b40(param_2,0,&uStack_38);
  if (cVar1 != '\0') {
    cVar1 = FUN_140897a60(param_2,1,&uStack_44);
    if (cVar1 != '\0') {
      cVar1 = FUN_140897a60(param_2,2,&uStack_40);
      if (cVar1 != '\0') {
        cVar1 = FUN_140897a60(param_2,3,&uStack_3c);
        if (cVar1 != '\0') {
          cVar1 = FUN_140897a60(param_2,4,&uStack_48);
          if (cVar1 != '\0') {
            cVar1 = FUN_140897a60(param_2,5,auStackX_18);
            if (cVar1 != '\0') {
              auStackX_20[0] = auStackX_18[0];
              lVar3 = FUN_140a9f870(param_2);
              if (6 < lVar3) {
                FUN_140897a60(param_2,6,auStackX_20);
              }
              uStack_34 = auStackX_18[0];
              uStack_30 = auStackX_18[0];
              uStack_2c = auStackX_20[0];
              uStack_1c = uStack_44;
              uStack_20 = uStack_48;
              uStack_14 = uStack_3c;
              uStack_18 = uStack_40;
              uStack_28 = 0;
              uVar2 = FUN_1405879d0(DAT_147a6b698,uStack_38,&uStack_1c,&uStack_28,&uStack_34);
              FUN_140a6b650(&DAT_1466e218c,uVar2);
              return;
            }
          }
        }
      }
    }
  }
  FUN_140897e40(0);
  return;
}



FUNCTION effect.DeleteEffect 14055dd50

void FUN_14055dd50(undefined8 param_1,undefined8 param_2)

{
  char cVar1;
  undefined4 auStackX_18 [4];
  
  cVar1 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar1 == '\0') {
    FUN_140897e40(0);
    return;
  }
  FUN_14057f820(DAT_147a6b698,auStackX_18[0]);
  FUN_140897f00();
  return;
}


