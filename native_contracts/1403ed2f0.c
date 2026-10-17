
ulonglong FUN_1403ed2f0(void)

{
  int iVar1;
  char *_Str;
  size_t sVar2;
  undefined4 extraout_var;

  if (*(char *)(DAT_147ccaa18 + 0x43a) != '\0') {
    return CONCAT71((int7)((ulonglong)DAT_147ccaa18 >> 8),1);
  }
  _Str = (char *)FUN_140535d40(DAT_147ccabd8);
  sVar2 = strlen(_Str);
  if (sVar2 != 0x15) {
    return sVar2 & 0xffffffffffffff00;
  }
  iVar1 = memcmp(_Str,"dungeons/spyral_abyss",0x15);
  return CONCAT71((int7)(CONCAT44(extraout_var,iVar1) >> 8),iVar1 == 0);
}
