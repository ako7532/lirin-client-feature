
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

longlong * FUN_140ae0f10(ulonglong param_1)

{
  longlong *plVar1;
  longlong lVar2;
  undefined8 *puVar3;
  longlong *plVar4;

  if ((longlong)param_1 < 0) {
    FUN_140af26b0("..\\external\\src\\python27\\Objects\\tupleobject.c",0x36);
    return (longlong *)0x0;
  }
  if (param_1 == 0) {
    plVar4 = DAT_147dfa860;
    if (DAT_147dfa860 != (longlong *)0x0) {
      *DAT_147dfa860 = *DAT_147dfa860 + 1;
      return plVar4;
    }
LAB_140ae0f6b:
    plVar4 = (&DAT_147dfa860)[param_1];
    if (plVar4 != (longlong *)0x0) {
      lVar2 = plVar4[3];
      *(int *)(&DAT_147dfa900 + param_1 * 4) = *(int *)(&DAT_147dfa900 + param_1 * 4) + -1;
      (&DAT_147dfa860)[param_1] = (longlong *)lVar2;
      *plVar4 = 1;
      goto LAB_140ae0fa1;
    }
  }
  else if ((longlong)param_1 < 0x14) goto LAB_140ae0f6b;
  if (((param_1 & 0x1fffffffffffffff) != param_1) || (0x7fffffffffffffd7 < param_1 * 8)) {
    plVar4 = (longlong *)FUN_140af1570();
    return plVar4;
  }
  plVar4 = (longlong *)FUN_140b3c620(&DAT_14754e100,param_1);
  if (plVar4 == (longlong *)0x0) {
    return (longlong *)0x0;
  }
LAB_140ae0fa1:
  if ((longlong)param_1 < 1) {
    _DAT_147dfa900 = _DAT_147dfa900 + 1;
    *plVar4 = *plVar4 + 1;
    DAT_147dfa860 = plVar4;
  }
  else {
    FUN_146872df0(plVar4 + 3,0,(param_1 * 8) / 8 << 3);
  }
  plVar1 = plVar4 + -3;
  if (plVar4[-1] == -2) {
    plVar4[-1] = -3;
    *plVar1 = (longlong)PTR_LOOP_147564cb8;
    puVar3 = *(undefined8 **)(PTR_LOOP_147564cb8 + 8);
    plVar4[-2] = (longlong)puVar3;
    *puVar3 = plVar1;
    *(longlong **)(PTR_LOOP_147564cb8 + 8) = plVar1;
    return plVar4;
  }
                    /* WARNING: Subroutine does not return */
  FUN_140af7220("GC object already tracked");
}
