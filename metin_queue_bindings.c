
FUNCTION player.MetinQueueAdd 1403f6360

void FUN_1403f6360(undefined8 param_1,undefined8 param_2)

{
  char cVar1;
  undefined1 uVar2;
  undefined4 auStackX_18 [4];
  
  cVar1 = FUN_140897b40(param_2,0,auStackX_18);
  if (cVar1 == '\0') {
    FUN_140897e40(0);
    return;
  }
  uVar2 = FUN_1403e41a0(DAT_147a6b6b0,auStackX_18[0]);
  FUN_140a6b650(&DAT_1466e218c,uVar2);
  return;
}



FUNCTION player.MetinQueueGetMaxSize 1403f63d0

void FUN_1403f63d0(void)

{
  int iVar1;
  
  iVar1 = FUN_1404e7da0(DAT_147a6b6d8,0x2ef,0);
  if (iVar1 != -1) {
    iVar1 = FUN_14018d030(DAT_147a6b358);
    FUN_140a6b650(&DAT_1466e218c,(9999 < iVar1) + '\x05');
    return;
  }
  FUN_140a6b650(&DAT_1466e218c,3);
  return;
}



FUNCTION player.MetinQueueGetSize 1403f6430
missing

FUNCTION player.MetinQueueIsEnabled 1403f6460
missing

FUNCTION player.MetinQueueSetEnabled 1403f6580

void FUN_1403f6580(undefined8 param_1,undefined8 param_2)

{
  char cVar1;
  bool bVar2;
  int aiStackX_18 [4];
  
  cVar1 = FUN_140897b40(param_2,0,aiStackX_18);
  if (cVar1 == '\0') {
    FUN_140897e40(0);
    return;
  }
  bVar2 = aiStackX_18[0] != 0;
  if (((bool)*(char *)(DAT_147a6b6b0 + 0x457c) != bVar2) &&
     (*(bool *)(DAT_147a6b6b0 + 0x457c) = bVar2, !bVar2)) {
    FUN_1403e4300();
  }
  FUN_140897f00();
  return;
}



FUNCTION CPythonPlayer.MetinQueueAdd 1403e41a0

undefined8 FUN_1403e41a0(longlong param_1,uint param_2)

{
  undefined4 *puVar1;
  uint *puVar2;
  char cVar3;
  int iVar4;
  undefined4 uVar5;
  undefined4 *puVar6;
  longlong lVar7;
  longlong *plVar8;
  ulonglong uVar9;
  ulonglong uVar10;
  uint auStackX_10 [2];
  undefined1 auStack_28 [16];
  
  auStackX_10[0] = param_2;
  puVar6 = (undefined4 *)
           thunk_FUN_1465bc990(*(undefined8 *)(param_1 + 0x4588),*(undefined8 *)(param_1 + 0x4590),
                               param_2);
  puVar1 = *(undefined4 **)(param_1 + 0x4590);
  if (puVar6 != puVar1) {
    return 1;
  }
  uVar10 = 0;
  for (puVar6 = *(undefined4 **)(param_1 + 0x4588); puVar6 != puVar1; puVar6 = puVar6 + 1) {
    cVar3 = FUN_1403d0860(*puVar6);
    uVar10 = uVar10 + (cVar3 == '\0');
  }
  iVar4 = FUN_1404e7da0(DAT_147a6b6d8,0x2ef,0);
  if (iVar4 == -1) {
    uVar9 = 3;
  }
  else {
    iVar4 = FUN_14018d030(DAT_147a6b358);
    uVar9 = (ulonglong)(9999 < iVar4) + 5;
  }
  if (uVar10 < uVar9) {
    lVar7 = FUN_1403d1d40(param_1,auStackX_10[0]);
    if (lVar7 != 0) {
      FUN_1404a95f0(lVar7,1);
    }
    puVar2 = *(uint **)(param_1 + 0x4590);
    if (puVar2 == *(uint **)(param_1 + 0x4598)) {
      FUN_140356550(param_1 + 0x4588,puVar2,auStackX_10);
    }
    else {
      *puVar2 = auStackX_10[0];
      *(longlong *)(param_1 + 0x4590) = *(longlong *)(param_1 + 0x4590) + 4;
    }
    uVar5 = FUN_140599020();
    plVar8 = (longlong *)FUN_140358ed0(param_1 + 0x45a0,auStack_28,auStackX_10);
    *(undefined4 *)(*plVar8 + 0x14) = uVar5;
    FUN_140243ac0(DAT_147a6b358,*(undefined1 *)(DAT_147a6b358 + 0x98));
    FUN_1404710d0(DAT_147a6ba20);
    return 1;
  }
  return 0;
}



FUNCTION CPythonPlayer.MetinQueueClear 1403e4300

void FUN_1403e4300(longlong param_1)

{
  longlong lVar1;
  undefined4 *puVar2;
  undefined4 *puVar3;
  
  puVar2 = *(undefined4 **)(param_1 + 0x4590);
  puVar3 = *(undefined4 **)(param_1 + 0x4588);
  if (puVar3 != puVar2) {
    do {
      lVar1 = FUN_1403d1d40(param_1,*puVar3);
      if (lVar1 != 0) {
        FUN_1404a95f0(lVar1,0);
      }
      puVar3 = puVar3 + 1;
    } while (puVar3 != puVar2);
    puVar2 = *(undefined4 **)(param_1 + 0x4590);
    puVar3 = *(undefined4 **)(param_1 + 0x4588);
  }
  if (*(int *)(param_1 + 0x433c) != 0) {
    lVar1 = thunk_FUN_1465bc990(puVar3,puVar2);
    if (lVar1 != *(longlong *)(param_1 + 0x4590)) {
      lVar1 = FUN_1403d1da0(param_1);
      if (lVar1 != 0) {
        FUN_1404a3660(lVar1);
        *(undefined4 *)(param_1 + 0xf8) = 0;
      }
      *(undefined4 *)(param_1 + 0xcc) = 0;
      FUN_1403eb4b0(param_1);
      *(undefined4 *)(param_1 + 0xec) = 0;
    }
  }
  if (*(longlong *)(param_1 + 0x4588) != *(longlong *)(param_1 + 0x4590)) {
    *(longlong *)(param_1 + 0x4590) = *(longlong *)(param_1 + 0x4588);
  }
  FUN_1402497f0(param_1 + 0x45a0);
  FUN_140243ac0(DAT_147a6b358,*(undefined1 *)(DAT_147a6b358 + 0x98));
  FUN_1404710d0(DAT_147a6ba20);
  return;
}


