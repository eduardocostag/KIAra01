param(
    [ValidateSet('All', 'OpenAI', 'OpenRouter', 'Groq', 'Gemini', 'Nvidia')]
    [string]$Provider = 'All',
    [switch]$FromClipboard
)

$ErrorActionPreference = 'Stop'

function Set-KiaraSecret {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Label
    )

    $pointer = [IntPtr]::Zero
    try {
        if ($FromClipboard) {
            $plainValue = Get-Clipboard -Raw
            Set-Clipboard -Value ''
        }
        else {
            $secureValue = Read-Host "Cole a chave $Label (Enter para nao alterar)" -AsSecureString
            $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
            $plainValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        }

        if ([string]::IsNullOrWhiteSpace($plainValue)) {
            Write-Warning "Nenhuma chave foi recebida para $Label."
            return
        }

        [Environment]::SetEnvironmentVariable($Name, $plainValue.Trim(), 'User')
        $saved = [Environment]::GetEnvironmentVariable($Name, 'User')
        if ([string]::IsNullOrWhiteSpace($saved)) {
            throw "Nao foi possivel persistir a chave $Label no perfil do Windows."
        }
        Write-Host "$Label configurado e verificado para o usuario atual."
    }
    finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
        $plainValue = $null
        $saved = $null
    }
}

if ($Provider -in @('All', 'Groq')) {
    Set-KiaraSecret -Name 'GROQ_API_KEY' -Label 'Groq'
}
if ($Provider -in @('All', 'Gemini')) {
    Set-KiaraSecret -Name 'GEMINI_API_KEY' -Label 'Gemini'
}
if ($Provider -in @('All', 'Nvidia')) {
    Set-KiaraSecret -Name 'NVIDIA_API_KEY' -Label 'NVIDIA NIM'
}
if ($Provider -in @('All', 'OpenAI')) {
    Set-KiaraSecret -Name 'OPENAI_API_KEY' -Label 'OpenAI'
}
if ($Provider -in @('All', 'OpenRouter')) {
    Set-KiaraSecret -Name 'OPENROUTER_API_KEY' -Label 'OpenRouter (Ox Alpha, Nemotron 3 Ultra e Ling 3.0 Flash)'
}

Write-Host 'Concluido. Feche e abra novamente a Kiara para carregar as chaves.'
