
longlong * FUN_140adb780(byte *param_1,ulonglong param_2)

{
  longlong *plVar1;
  ulonglong uVar2;
  longlong *plStackX_10;

  if ((longlong)param_2 < 0) {
    FUN_140af20e0(PTR_DAT_147556318,"Negative size passed to PyString_FromStringAndSize");
    return (longlong *)0x0;
  }
  if (param_2 == 0) {
    plVar1 = DAT_147dfa850;
    if (DAT_147dfa850 != (longlong *)0x0) {
      *DAT_147dfa850 = *DAT_147dfa850 + 1;
      return plVar1;
    }
  }
  else if (param_2 == 1) {
    if (param_1 != (byte *)0x0) {
      plVar1 = (longlong *)(&DAT_147dfa050)[*param_1];
      if (plVar1 != (longlong *)0x0) {
        *plVar1 = *plVar1 + 1;
        return plVar1;
      }
    }
  }
  else if (0x7fffffffffffffde < param_2) {
    FUN_140af20e0(PTR_DAT_147555828,"string is too large");
    return (longlong *)0x0;
  }
  plVar1 = (longlong *)FUN_140ab84e0();
  if (plVar1 == (longlong *)0x0) {
    plStackX_10 = (longlong *)FUN_140af1570();
  }
  else {
    plVar1[2] = param_2;
    plVar1[1] = (longlong)&DAT_14754d7a0;
    *plVar1 = 1;
    *(undefined4 *)(plVar1 + 3) = 0xffffffff;
    *(undefined4 *)((longlong)plVar1 + 0x1c) = 0;
    if (param_1 != (byte *)0x0) {
      if (param_2 < 0x10) {
        uVar2 = 0;
        if (param_2 != 0) {
          do {
            *(byte *)((longlong)plVar1 + uVar2 + 0x20) = param_1[uVar2];
            uVar2 = uVar2 + 1;
          } while (uVar2 < param_2);
        }
      }
      else {
        FUN_1468725c0(plVar1 + 4,param_1,param_2);
      }
    }
    *(undefined1 *)((longlong)plVar1 + param_2 + 0x20) = 0;
    plStackX_10 = plVar1;
    if (param_2 == 0) {
      FUN_140adb960(&plStackX_10);
      DAT_147dfa850 = plStackX_10;
    }
    else {
      if (param_2 != 1) {
        return plVar1;
      }
      if (param_1 == (byte *)0x0) {
        return plVar1;
      }
      FUN_140adb960(&plStackX_10);
      (&DAT_147dfa050)[*param_1] = plStackX_10;
    }
    *plStackX_10 = *plStackX_10 + 1;
  }
  return plStackX_10;
}
