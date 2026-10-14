# Opt-in only. Return application category/control bounds, never titles or text.
Add-Type @'
using System; using System.Runtime.InteropServices;
public class PaitForeground {
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint p);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h,System.Text.StringBuilder s,int n);
}
'@
$windowHandle=[PaitForeground]::GetForegroundWindow()
[uint32]$foregroundProcessId=0
[void][PaitForeground]::GetWindowThreadProcessId($windowHandle,[ref]$foregroundProcessId)
$processName=(Get-Process -Id $foregroundProcessId -ErrorAction SilentlyContinue).ProcessName
$kind='other'
if($processName -match '^(WINWORD|EXCEL|POWERPNT|notepad|wps|Code)$'){$kind='document'}
if($processName -match '^(vlc|PotPlayerMini64|PotPlayerMini|wmplayer|MediaPlayer)$'){$kind='video'}
$result=@{kind=$kind}
$className=New-Object System.Text.StringBuilder 256
[void][PaitForeground]::GetClassName($windowHandle,$className,256)
if($className.ToString() -in @('Progman','WorkerW')){
 try {
  Add-Type -AssemblyName UIAutomationClient
  Add-Type -AssemblyName UIAutomationTypes
  $root=[System.Windows.Automation.AutomationElement]::FromHandle($windowHandle)
  $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::ListItem)
  $items=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
  if($items.Count -gt 0){
   $item=$items.Item((Get-Random -Minimum 0 -Maximum ([Math]::Min(64,$items.Count))))
   $bounds=$item.Current.BoundingRectangle
   if(!$bounds.IsEmpty -and !$item.Current.IsOffscreen){$result.kind='desktop';$result.bounds=@{x=$bounds.X+$bounds.Width/2;y=$bounds.Y+$bounds.Height}}
  }
 }catch{}
}
if($kind -eq 'video'){
 try {
  Add-Type -AssemblyName UIAutomationClient
  Add-Type -AssemblyName UIAutomationTypes
  $root=[System.Windows.Automation.AutomationElement]::FromHandle($windowHandle)
  $condition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Slider)
  $sliders=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)
  foreach($slider in $sliders){
   if($slider.Current.Name -match '进度|播放位置|seek|position|timeline'){
    $bounds=$slider.Current.BoundingRectangle
    if(!$bounds.IsEmpty -and !$slider.Current.IsOffscreen){$result.bounds=@{x=$bounds.X;y=$bounds.Y};break}
   }
  }
 }catch{}
}
$result | ConvertTo-Json -Compress
