#define UNICODE
#define _UNICODE
#include <windows.h>
#include <wchar.h>
#include <stdio.h>

/* No shell, external runtime, token or secret argument. All paths come from this executable. */
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE previous, LPWSTR tail, int show) {
    wchar_t root[32768], python[32768], command[32768];
    STARTUPINFOW start = {0}; PROCESS_INFORMATION process = {0};
    SECURITY_ATTRIBUTES security = {sizeof(SECURITY_ATTRIBUTES), NULL, TRUE};
    HANDLE nul, appMutex; DWORD result;
    (void)instance; (void)previous; (void)show;
    if (!GetModuleFileNameW(NULL, root, 32768)) return 1;
    wchar_t *end = wcsrchr(root, L'\\');
    if (!end) return 1;
    *end = 0;
    if (swprintf_s(python, 32768, L"%ls\\runtime\\python.exe", root) < 0 ||
        swprintf_s(command, 32768, L"\"%ls\" -I \"%ls\\launcher.py\" --desktop%ls", python, root, _wcsicmp(tail, L"--no-browser") == 0 ? L" --no-browser" : L"") < 0) return 1;
    nul = CreateFileW(L"NUL", GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                     &security, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (nul == INVALID_HANDLE_VALUE) return 1;
    appMutex = CreateMutexW(NULL, FALSE, L"Local\\HUGINN-IA-Installed");
    if (!appMutex) { CloseHandle(nul); return 1; }
    start.cb = sizeof(start); start.dwFlags = STARTF_USESTDHANDLES;
    start.hStdInput = nul; start.hStdOutput = nul; start.hStdError = nul;
    if (!CreateProcessW(python, command, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, root, &start, &process)) {
        CloseHandle(nul); CloseHandle(appMutex);
        if (_wcsicmp(tail, L"--no-browser") != 0) MessageBoxW(NULL, L"Instalacao incompleta. Reinstale o HUGINN usando o instalador verificado. Nao e necessario reiniciar o Windows.", L"HUGINN IA", MB_ICONERROR);
        return 1;
    }
    CloseHandle(nul); CloseHandle(process.hThread);
    WaitForSingleObject(process.hProcess, INFINITE);
    GetExitCodeProcess(process.hProcess, &result); CloseHandle(process.hProcess); CloseHandle(appMutex);
    return (int)result;
}
