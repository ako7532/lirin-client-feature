
void FUN_140ace140(int param_1)

{
  undefined8 *puVar1;

  if (param_1 + 5U < 0x106) {
    **(longlong **)(&DAT_147df9368 + (longlong)param_1 * 8) =
         **(longlong **)(&DAT_147df9368 + (longlong)param_1 * 8) + 1;
    return;
  }
  puVar1 = DAT_147df9338;
  if (DAT_147df9338 == (undefined8 *)0x0) {
    puVar1 = (undefined8 *)FUN_140ace830();
    DAT_147df9338 = puVar1;
    if (puVar1 == (undefined8 *)0x0) {
      return;
    }
  }
  DAT_147df9338 = (undefined8 *)puVar1[1];
  puVar1[1] = &DAT_147549c90;
  *puVar1 = 1;
  *(int *)(puVar1 + 2) = param_1;
  return;
}
