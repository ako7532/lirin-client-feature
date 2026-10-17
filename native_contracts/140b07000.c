
longlong FUN_140b07000(longlong param_1)

{
  int iVar1;
  longlong lVar2;

  if (*(undefined **)(param_1 + 8) != &DAT_147551e70) {
    iVar1 = FUN_140ab1130();
    if (iVar1 == 0) {
      FUN_140af26b0("..\\external\\src\\python27\\Objects\\moduleobject.c",0x32);
      return 0;
    }
  }
  lVar2 = *(longlong *)(param_1 + 0x10);
  if (lVar2 == 0) {
    lVar2 = FUN_140ae8ae0();
    *(longlong *)(param_1 + 0x10) = lVar2;
  }
  return lVar2;
}
