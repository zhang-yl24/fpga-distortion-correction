function Assert-LiveTemperature {
    param([string]$Line,[double]$ElapsedSeconds,[double]$LimitC=85)
    $fields=@{}
    foreach($match in [regex]::Matches($Line,'\b(TV|TR|TF|TA|AL)=([0-9A-Fa-f]+)\b')) {
        if($fields.ContainsKey($match.Groups[1].Value)){throw 'Duplicate temperature field'}
        $fields[$match.Groups[1].Value]=[Convert]::ToUInt32($match.Groups[2].Value,16)
    }
    foreach($key in @('TV','TR','TF','TA','AL')) {
        if(!$fields.ContainsKey($key)){throw "Missing temperature field: $key"}
    }
    # Alarms stop a run immediately, including startup. Valid sample checks
    # allow a four-second bias/conversion/readback startup window.
    if($fields.AL -band 0x20){throw 'ADC hardware over-temperature flag asserted'}
    if($fields.TV -eq 1) {
        if($fields.TR -gt 65535 -or ($fields.TR -shr 4) -eq 0){throw 'Invalid ADC word'}
        $c=($fields.TR -shr 4)*0.1219-273.15
        if($c -gt $LimitC){throw ('ADC estimate {0:F2} C exceeds diagnostic limit {1} C' -f $c,$LimitC)}
        if($c -lt -40 -or $c -gt 125){throw 'Implausible ADC temperature estimate'}
    }
    if($ElapsedSeconds -ge 4) {
        if($fields.TV -ne 1 -or $fields.TF -ne 0 -or $fields.TA -ge 54000000 -or
           ($fields.AL -band 0x40) -or !($fields.AL -band 0x80)) {
            throw 'Temperature sample is invalid, faulty or stale; ending heavy test'
        }
    }
}
