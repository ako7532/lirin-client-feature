
int FUN_140aa6180(char *param_1,int param_2)

{
  int iVar1;
  int iVar2;

  iVar2 = 0;
  iVar1 = 0;
  while ((0 < iVar1 || (*param_1 != param_2))) {
    switch(*param_1) {
    case '\0':
      FUN_140af20e0(PTR_DAT_147556318,"unmatched paren in format");
      return -1;
    default:
      if (iVar1 == 0) {
        iVar2 = iVar2 + 1;
      }
    case '\t':
    case ' ':
    case '#':
    case '&':
    case ',':
    case ':':
      param_1 = param_1 + 1;
      break;
    case '(':
    case '[':
    case '{':
      iVar2 = iVar2 + (uint)(iVar1 == 0);
      iVar1 = iVar1 + 1;
      param_1 = param_1 + 1;
      break;
    case ')':
    case ']':
    case '}':
      iVar1 = iVar1 + -1;
      param_1 = param_1 + 1;
    }
  }
  return iVar2;
}
