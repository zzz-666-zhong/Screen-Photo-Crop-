using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using Crop.Core;
using Microsoft.Win32;
using OpenCvSharp;

namespace Crop.Desktop;

public sealed class PhotoCard(BatchEngine engine, PhotoRecord record) : INotifyPropertyChanged
{
    public PhotoRecord Record { get; } = record;
    public string Name => Path.GetFileName(Record.RelativePath);
    public PhotoState State => Record.State;
    public string Reason => string.Join(" · ",Record.Reasons);
    public string StatusText => Record.State switch { PhotoState.Pending=>"未处理",PhotoState.Processing=>"定位中…",PhotoState.AutoAccepted=>"自动通过",PhotoState.NeedsReview=>"待复核",PhotoState.Confirmed=>"人工确认",PhotoState.Rejected=>"拍摄失败 · 已排除",_=>"处理失败" };
    public string ThumbnailPath => (engine.OutputPath(Record) is string output && File.Exists(output)?output:engine.SourcePath(Record))+"|"+(Record.UpdatedAt?.Ticks??0);
    public string BoundaryKey => engine.SourcePath(Record)+"|"+(Record.UpdatedAt?.Ticks??0)+"|"+Record.Width+"|"+Record.Height+"|"+string.Join(';',(Record.Corners??[]).Select(p=>p.X.ToString(CultureInfo.InvariantCulture)+","+p.Y.ToString(CultureInfo.InvariantCulture)));
    private bool selected;
    public bool Selected {get=>selected;set {selected=value;Changed(nameof(Selected));}}
    public event PropertyChangedEventHandler? PropertyChanged;
    private void Changed(string property)=>PropertyChanged?.Invoke(this,new(property));
    public void Refresh(){Changed(nameof(State));Changed(nameof(StatusText));Changed(nameof(Reason));Changed(nameof(ThumbnailPath));Changed(nameof(BoundaryKey));}
}
public sealed class StateBrushConverter : IValueConverter
{
    public object Convert(object value,Type type,object parameter,CultureInfo culture)=>new SolidColorBrush((System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString(value is PhotoState.NeedsReview?"#AD6C25":value is PhotoState.Error or PhotoState.Rejected?"#B14836":value is PhotoState.AutoAccepted or PhotoState.Confirmed?"#5D7550":"#777D74"));
    public object ConvertBack(object value,Type type,object parameter,CultureInfo culture)=>throw new NotSupportedException();
}
public sealed class ThumbConverter : IValueConverter
{
    private static readonly Dictionary<string,BitmapSource> Cache=[];
    private static readonly Queue<string> Keys=[];
    public object? Convert(object value,Type type,object parameter,CultureInfo culture)
    {
        string key=value as string??"";if(Cache.TryGetValue(key,out var cached))return cached;
        try
        {
            string path=key.Split('|')[0];using var stream=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite);
            ushort orientation=1;
            if(Path.GetExtension(path).Equals(".jpg",StringComparison.OrdinalIgnoreCase)||Path.GetExtension(path).Equals(".jpeg",StringComparison.OrdinalIgnoreCase))
            {
                try{var decoder=BitmapDecoder.Create(stream,BitmapCreateOptions.DelayCreation,BitmapCacheOption.OnDemand);if(decoder.Frames[0].Metadata is BitmapMetadata metadata&&metadata.ContainsQuery("/app1/ifd/{ushort=274}"))orientation=System.Convert.ToUInt16(metadata.GetQuery("/app1/ifd/{ushort=274}"));}
                catch(Exception ex) when(ex is NotSupportedException or FileFormatException){}stream.Position=0;
            }
            var bitmap=new BitmapImage();bitmap.BeginInit();bitmap.CacheOption=BitmapCacheOption.OnLoad;bitmap.DecodePixelWidth=260;bitmap.Rotation=orientation switch{3=>Rotation.Rotate180,5 or 6=>Rotation.Rotate90,7 or 8=>Rotation.Rotate270,_=>Rotation.Rotate0};bitmap.StreamSource=stream;bitmap.EndInit();bitmap.Freeze();
            BitmapSource result=bitmap;
            if(orientation is 2 or 4 or 5 or 7){result=new TransformedBitmap(bitmap,new ScaleTransform(orientation==4?1:-1,orientation==4?-1:1));result.Freeze();}
            Cache[key]=result;Keys.Enqueue(key);while(Keys.Count>80)Cache.Remove(Keys.Dequeue());return result;
        }
        catch(Exception ex) when(ex is IOException or NotSupportedException or FileFormatException){return null;}
    }
    public object ConvertBack(object value,Type type,object parameter,CultureInfo culture)=>throw new NotSupportedException();
}
public sealed class BoundaryThumbConverter : IValueConverter
{
    private static readonly Dictionary<string,BitmapSource> Cache=[];
    private static readonly Queue<string> Keys=[];
    private readonly ThumbConverter thumbnails=new();
    public object? Convert(object value,Type type,object parameter,CultureInfo culture)
    {
        if(value is not string key)return null;if(Cache.TryGetValue(key,out var cached))return cached;
        var parts=key.Split('|');
        if(thumbnails.Convert(parts[0]+"|"+parts[1],type,parameter,culture) is not BitmapSource bitmap)return null;
        if(parts.Length<5||!int.TryParse(parts[2],out int width)||!int.TryParse(parts[3],out int height)||width==0||height==0||string.IsNullOrEmpty(parts[4]))return bitmap;
        var points=parts[4].Split(';').Select(v=>v.Split(',')).Select(v=>new System.Windows.Point(double.Parse(v[0],CultureInfo.InvariantCulture)/width*bitmap.PixelWidth,double.Parse(v[1],CultureInfo.InvariantCulture)/height*bitmap.PixelHeight)).ToArray();
        var visual=new DrawingVisual();using(var dc=visual.RenderOpen())
        {
            dc.DrawImage(bitmap,new System.Windows.Rect(0,0,bitmap.PixelWidth,bitmap.PixelHeight));
            var geometry=new StreamGeometry();using(var context=geometry.Open()){context.BeginFigure(points[0],true,true);context.PolyLineTo(points.Skip(1).ToArray(),true,false);}
            var color=System.Windows.Media.Color.FromRgb(243,177,79);dc.DrawGeometry(new SolidColorBrush(System.Windows.Media.Color.FromArgb(12,243,177,79)),new Pen(new SolidColorBrush(color),1.6),geometry);
            foreach(var p in points)dc.DrawEllipse(new SolidColorBrush(color),new Pen(Brushes.Black,.7),p,2.5,2.5);
        }
        var result=new RenderTargetBitmap(bitmap.PixelWidth,bitmap.PixelHeight,96,96,PixelFormats.Pbgra32);result.Render(visual);result.Freeze();Cache[key]=result;Keys.Enqueue(key);while(Keys.Count>80)Cache.Remove(Keys.Dequeue());return result;
    }
    public object ConvertBack(object value,Type type,object parameter,CultureInfo culture)=>throw new NotSupportedException();
}
public partial class MainWindow : System.Windows.Window
{
    private BatchEngine? engine;
    private List<PhotoCard> cards=[];
    private List<PhotoCard> filtered=[];
    private int page;
    private const int PageSize=12;
    private PhotoCard? current;
    private readonly HashSet<PhotoRecord> reviewVisited=[];
    private bool initialized,editing,dirty,closingRequested;
    private int previewGeneration,editorGeneration;
    private readonly Stopwatch timer=new();
    private string PreferencesPath=>Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"ScreenCrop","preferences.json");
    public MainWindow()
    {
        InitializeComponent();initialized=true;
        Surface.PointsChanged+=Surface_Changed;
        PreviewKeyDown+=Window_KeyDown;
        try { if(File.Exists(PreferencesPath)){var data=System.Text.Json.JsonSerializer.Deserialize<Dictionary<string,string>>(File.ReadAllText(PreferencesPath));SourceBox.Text=data?.GetValueOrDefault("source","");OutputBox.Text=data?.GetValueOrDefault("output","");} }
        catch(Exception ex) when(ex is IOException or System.Text.Json.JsonException){}
    }
    private void SetEditing(bool value)
    {
        editing=value;EditorPanel.IsEnabled=!value;RunButton.IsEnabled=!value;RetryButton.IsEnabled=!value;AcceptSelectedButton.IsEnabled=!value;
    }
    private void Say(string message)=>StatusLine.Text=message;
    private bool Available()=>!(engine?.IsRunning??false)&&!editing;
    private void RefreshStats()
    {
        if(engine is null)return;var photos=engine.Batch.Photos;
        TotalText.Text=photos.Count.ToString();AutoText.Text=photos.Count(p=>p.State==PhotoState.AutoAccepted).ToString();ReviewText.Text=photos.Count(p=>p.State==PhotoState.NeedsReview).ToString();
        ConfirmedText.Text=$"{photos.Count(p=>p.State==PhotoState.Confirmed)} / {photos.Count(p=>p.State==PhotoState.Error)}";
        Progress.Value=photos.Count(p=>p.State is not (PhotoState.Pending or PhotoState.Processing))*100d/photos.Count;
    }
    private void Attach(BatchEngine batch)
    {
        engine=batch;cards=batch.Batch.Photos.Select(p=>new PhotoCard(batch,p)).ToList();page=0;current=null;
        SourceBox.Text=batch.Batch.Source;OutputBox.Text=batch.Batch.Destination;SquareBox.IsChecked=batch.Batch.Options.Square;RecursiveBox.IsChecked=batch.Batch.Options.Recursive;InsetBox.Text=batch.Batch.Options.InsetPixels.ToString();
        SizeBox.SelectedIndex=Array.IndexOf(new[]{0,128,256,400,512},batch.Batch.Options.OutputSize);
        SetupPanel.IsEnabled=false;LockedHint.Visibility=Visibility.Visible;ResultsButton.IsEnabled=true;RunButton.Content="继续处理未完成照片  →";
        Subtitle.Text=$"{Path.GetFileName(batch.Batch.Source)}  /  {batch.Batch.Photos.Count} 张照片";
        EditorPanel.Visibility=Visibility.Collapsed;OverviewPanel.Visibility=Visibility.Visible;BackButton.Visibility=Visibility.Collapsed;
        RefreshStats();ApplyFilter();
    }
    private void ApplyFilter()
    {
        if(!initialized)return;
        string query=SearchBox.Text.Trim();int filter=FilterBox.SelectedIndex;
        filtered=cards.Where(c=>c.Record.RelativePath.Contains(query,StringComparison.OrdinalIgnoreCase)).Where(c=>filter switch {1=>c.State==PhotoState.NeedsReview,2=>c.State==PhotoState.AutoAccepted,3=>c.State==PhotoState.Confirmed,4=>c.State==PhotoState.Error,5=>c.State is PhotoState.Pending or PhotoState.Processing,6=>c.State==PhotoState.Rejected,_=>true}).ToList();
        page=Math.Clamp(page,0,Math.Max(0,(filtered.Count-1)/PageSize));PhotoGrid.ItemsSource=filtered.Skip(page*PageSize).Take(PageSize).ToList();
        PageInfo.Text=engine is null?"尚未导入照片":$"{filtered.Count} 张符合筛选 · 第 {page+1} / {Math.Max(1,(filtered.Count+PageSize-1)/PageSize)} 页";
        EmptyPanel.Visibility=filtered.Count==0?Visibility.Visible:Visibility.Collapsed;
        EmptyTitle.Text=engine is null?"让一整批照片自己跑完":"当前筛选没有照片";
        EmptyDetail.Text=engine is null?"选择左侧原照片和结果目录，点击开始整批处理。可靠结果自动导出，疑难照片集中复核。":"换一个筛选条件，或等待本批处理完成。";
    }
    private void Filter_Changed(object sender,SelectionChangedEventArgs e){page=0;ApplyFilter();}
    private void Search_Changed(object sender,TextChangedEventArgs e){page=0;ApplyFilter();}
    private void PrevPage_Click(object sender,RoutedEventArgs e){page=Math.Max(0,page-1);ApplyFilter();}
    private void NextPage_Click(object sender,RoutedEventArgs e){page++;ApplyFilter();}
    private static string? Folder(string title){var dialog=new OpenFolderDialog {Title=title,Multiselect=false};return dialog.ShowDialog()==true?dialog.FolderName:null;}
    private void Source_Click(object sender,RoutedEventArgs e){string? folder=Folder("选择抖动原照片目录");if(folder is null)return;SourceBox.Text=folder;if(string.IsNullOrWhiteSpace(OutputBox.Text))OutputBox.Text=folder+"_裁剪结果";}
    private void Output_Click(object sender,RoutedEventArgs e){string? folder=Folder("选择结果保存位置");if(folder is not null)OutputBox.Text=folder;}
    private void Path_Drop(object sender,DragEventArgs e){if(!Available()||!SetupPanel.IsEnabled)return;if(e.Data.GetData(DataFormats.FileDrop) is string[] paths&&paths.Length>0&&Directory.Exists(paths[0])){SourceBox.Text=paths[0];if(string.IsNullOrWhiteSpace(OutputBox.Text))OutputBox.Text=paths[0]+"_裁剪结果";}}
    private bool DiscardEdits()=>!dirty||MessageBox.Show(this,"当前四角尚未保存。放弃这次调整？","未保存的调整",MessageBoxButton.YesNo,MessageBoxImage.Question)==MessageBoxResult.Yes;
    private void New_Click(object sender,RoutedEventArgs e)
    {
        if(!Available()){Say("请等待当前操作结束。");return;}if(!DiscardEdits())return;
        engine=null;cards=[];filtered=[];current=null;dirty=false;editorGeneration++;previewGeneration++;Surface.Clear();PreviewImage.Source=null;
        SetupPanel.IsEnabled=true;LockedHint.Visibility=Visibility.Collapsed;ResultsButton.IsEnabled=false;RunButton.Content="开始整批处理  →";TotalText.Text="—";AutoText.Text=ReviewText.Text="0";ConfirmedText.Text="0 / 0";Progress.Value=0;
        EditorPanel.Visibility=Visibility.Collapsed;OverviewPanel.Visibility=Visibility.Visible;BackButton.Visibility=Visibility.Collapsed;Subtitle.Text="把时间留给疑难照片";ApplyFilter();Say("选择新批次的目录与参数。");
    }
    private async void Open_Click(object sender,RoutedEventArgs e)
    {
        if(!Available()||!DiscardEdits())return;string? folder=Folder("打开包含 batch_session.json 的结果目录");if(folder is not null)await OpenBatchAsync(folder);
    }
    public async Task OpenBatchAsync(string folder)
    {
        try{SetEditing(true);var batch=await Task.Run(()=>BatchEngine.Open(folder));Attach(batch);dirty=false;Say("已打开批次 · 待复核结果已保留，可继续处理或直接复核。");}
        catch(Exception ex){Say(ex.Message);}finally{SetEditing(false);}
    }
    private async void Run_Click(object sender,RoutedEventArgs e)
    {
        if(!Available()||!DiscardEdits())return;
        try
        {
            if(engine is null)
            {
                if(!int.TryParse(InsetBox.Text,out int inset))throw new ArgumentException("内切像素必须是整数。");
                int output=int.Parse(((ComboBoxItem)SizeBox.SelectedItem).Tag.ToString()!);
                var options=new CropOptions(SquareBox.IsChecked==true,RecursiveBox.IsChecked==true,output,inset);
                string source=SourceBox.Text.Trim(),destination=OutputBox.Text.Trim();if(string.IsNullOrWhiteSpace(destination))throw new ArgumentException("请填写结果目录。");
                SetEditing(true);var batch=await Task.Run(()=>BatchEngine.Create(source,destination,options));Attach(batch);SetEditing(false);
                Store.WriteJson(PreferencesPath,new Dictionary<string,string>{{"source",source},{"output",destination}});
            }
            if(!engine!.Batch.Photos.Any(p=>p.State==PhotoState.Pending)){Say("没有未处理照片。可筛选“待复核”集中检查，或新建批次。");return;}
            dirty=false;OverviewPanel.Visibility=Visibility.Visible;EditorPanel.Visibility=Visibility.Collapsed;BackButton.Visibility=Visibility.Collapsed;
            RunButton.Visibility=Visibility.Collapsed;PauseButton.Visibility=Visibility.Visible;AcceptSelectedButton.IsEnabled=false;timer.Restart();
            var progress=new Progress<BatchProgress>(p=>{var card=cards[p.Index-1];card.Refresh();RefreshStats();ApplyFilter();Say($"{p.Index} / {p.Total} · {p.Photo.RelativePath} · {card.StatusText}");ElapsedText.Text=$"已用 {timer.Elapsed:mm\\:ss}";});
            await engine.RunAsync(progress);
            timer.Stop();RefreshStats();ApplyFilter();
            int pending=engine.Batch.Photos.Count(p=>p.State==PhotoState.Pending),review=engine.Batch.Photos.Count(p=>p.State==PhotoState.NeedsReview);
            Say(pending>0?$"已暂停 · 剩余 {pending} 张，点击继续即可恢复。":$"整批处理完成 · {review} 张待复核。结果与记录已保存。");
        }
        catch(Exception ex){Say("处理未完成："+ex.Message);}
        finally{SetEditing(false);RunButton.Visibility=Visibility.Visible;PauseButton.Visibility=Visibility.Collapsed;PauseButton.IsEnabled=true;AcceptSelectedButton.IsEnabled=true;if(closingRequested)Close();}
    }
    private async void Retry_Click(object sender,RoutedEventArgs e)
    {
        if(engine is null||!Available())return;
        try{SetEditing(true);await Task.Run(()=>engine.RetryErrors());foreach(var card in cards)card.Refresh();RefreshStats();ApplyFilter();}
        catch(Exception ex){Say(ex.Message);return;}finally{SetEditing(false);}
        Run_Click(sender,e);
    }
    private void Pause_Click(object sender,RoutedEventArgs e){engine?.RequestStop();PauseButton.IsEnabled=false;Say("正在完成当前照片并保存进度，随后暂停…");}
    private void Results_Click(object sender,RoutedEventArgs e){if(engine is not null)Process.Start(new ProcessStartInfo("explorer.exe",engine.Batch.Destination){UseShellExecute=true});}
    private void SelectPage_Click(object sender,RoutedEventArgs e)
    {
        var visible=filtered.Skip(page*PageSize).Take(PageSize).Where(c=>c.Record.Corners?.Length==4&&c.State is PhotoState.NeedsReview or PhotoState.AutoAccepted).ToList();bool select=visible.Any(c=>!c.Selected);foreach(var c in visible)c.Selected=select;
        Say($"已选择 {cards.Count(c=>c.Selected)} 张；确认所选会将这些结果标为人工确认。");
    }
    private async void AcceptSelected_Click(object sender,RoutedEventArgs e)
    {
        if(engine is null||!Available())return;var selected=cards.Where(c=>c.Selected).ToList();if(selected.Count==0){Say("请先勾选已经检查过的照片。");return;}
        SetEditing(true);AcceptSelectedButton.IsEnabled=false;
        try{foreach(var c in selected){if(c.Record.Corners?.Length!=4||c.State is PhotoState.Error or PhotoState.Pending or PhotoState.Rejected)continue;await Task.Run(()=>engine.Accept(c.Record,c.Record.Corners));c.Selected=false;c.Refresh();}RefreshStats();ApplyFilter();Say("所选照片已确认保存。");}
        catch(Exception ex){Say("确认未完成："+ex.Message);}finally{SetEditing(false);AcceptSelectedButton.IsEnabled=true;}
    }
    private async void Photo_Click(object sender,RoutedEventArgs e){if(sender is Button {Tag:PhotoCard card})await OpenPhotoAsync(card);}
    public Task OpenFirstAsync()=>cards.Count==0?Task.CompletedTask:OpenPhotoAsync(cards[0]);
    private async Task OpenPhotoAsync(PhotoCard card)
    {
        if(engine is null||!Available()||!DiscardEdits())return;
        if(EditorPanel.Visibility!=Visibility.Visible)reviewVisited.Clear();
        int generation=++editorGeneration;previewGeneration++;SetEditing(true);current=card;dirty=false;PreviewImage.Source=null;
        OverviewPanel.Visibility=Visibility.Collapsed;EditorPanel.Visibility=Visibility.Visible;BackButton.Visibility=Visibility.Visible;
        EditorName.Text=card.Record.RelativePath;ReasonText.Text=card.Reason.Length>0?card.Reason:card.State==PhotoState.AutoAccepted?"四边证据满足当前自动规则，仍可检查或调整。":"检查完整图片边界，确认后保存。";SaveNextButton.IsEnabled=false;
        try
        {
            var bitmap=await Task.Run(()=>{using var image=Store.LoadImage(engine.SourcePath(card.Record));return ToBitmap(image);});
            if(generation!=editorGeneration)return;
            Surface.SetImage(bitmap,card.Record.Corners);SaveNextButton.IsEnabled=card.Record.Corners?.Length==4;await PreviewAsync();
        }
        catch(Exception ex){Say("打开失败："+ex.Message);Surface.Clear();}
        finally{SetEditing(false);}
    }
    private async void Surface_Changed(object? sender,EventArgs e){dirty=true;SaveNextButton.IsEnabled=Surface.Points.Count==4;if(Surface.Points.Count==4)await PreviewAsync();else{previewGeneration++;PreviewImage.Source=null;PreviewInfo.Text=$"已选 {Surface.Points.Count} / 4 个角点";}}
    private async Task PreviewAsync()
    {
        if(engine is null||current is null||Surface.Points.Count!=4)return;
        int generation=++previewGeneration;string path=engine.SourcePath(current.Record);var points=Surface.Points.ToArray();var options=engine.Batch.Options;
        try{var result=await Task.Run(()=>{using var image=Store.LoadImage(path);using var crop=Store.Rectify(image,points.Select(p=>p.ToCv()).ToArray(),options);return (Bitmap:ToBitmap(crop),crop.Width,crop.Height);});if(generation!=previewGeneration)return;PreviewImage.Source=result.Bitmap;PreviewInfo.Text=$"{result.Width} × {result.Height} px · 内切 {options.InsetPixels} px";}
        catch(Exception ex){if(generation==previewGeneration){PreviewImage.Source=null;PreviewInfo.Text=ex.Message;SaveNextButton.IsEnabled=false;}}
    }
    private async void Detect_Click(object sender,RoutedEventArgs e)
    {
        if(engine is null||current is null||!Available())return;SetEditing(true);var card=current;
        try{var result=await Task.Run(()=>{using var image=Store.LoadImage(engine.SourcePath(card.Record));return new FrameDetector().Detect(image,engine.Batch.Options.Square);});
            if(result.Corners is null){ReasonText.Text=string.Join("；",result.Reasons);Say("未找到可靠边界，请手动选择四角。");}
            else{Surface.SetPoints(PixelPoint.From(result.Corners));dirty=true;ReasonText.Text=result.Automatic?"已重新定位，请检查后确认。":string.Join("；",result.Reasons);SaveNextButton.IsEnabled=true;await PreviewAsync();}}
        catch(Exception ex){Say(ex.Message);}finally{SetEditing(false);}
    }
    private async void SaveNext_Click(object sender,RoutedEventArgs e)=>await SaveNextAsync();
    private async Task SaveNextAsync()
    {
        if(engine is null||current is null||!Available()||Surface.Points.Count!=4||Surface.IsInteracting)return;
        SetEditing(true);SaveNextButton.IsEnabled=false;var card=current;var corners=Surface.Points.ToArray();
        try{await Task.Run(()=>engine.Accept(card.Record,corners));card.Refresh();dirty=false;RefreshStats();Say("已确认保存："+card.Name);}
        catch(Exception ex){Say("保存失败："+ex.Message);return;}
        finally{SetEditing(false);SaveNextButton.IsEnabled=Surface.Points.Count==4;}
        await NextReviewAsync();
    }
    private async Task NextReviewAsync()
    {
        if(current is null)return;reviewVisited.Add(current.Record);var queue=cards.Where(c=>c.State is PhotoState.NeedsReview or PhotoState.Error).Where(c=>!reviewVisited.Contains(c.Record)).ToList();
        var next=queue.FirstOrDefault(c=>cards.IndexOf(c)>cards.IndexOf(current))??queue.FirstOrDefault(c=>c!=current);
        if(next is null){int remaining=cards.Count(c=>c.State is PhotoState.NeedsReview or PhotoState.Error);BackToOverview();Say(remaining==0?"当前疑难队列已检查完毕。可在总览查看全部结果。":$"本轮浏览结束 · 仍有 {remaining} 张待复核或处理失败，可在总览继续检查。");}else await OpenPhotoAsync(next);
    }
    private async void Skip_Click(object sender,RoutedEventArgs e){if(!Available()||!DiscardEdits())return;dirty=false;await NextReviewAsync();}
    private async void Reject_Click(object sender,RoutedEventArgs e)
    {
        if(engine is null||current is null||!Available())return;SetEditing(true);
        try{var card=current;await Task.Run(()=>engine.Reject(card.Record,"人工标记拍摄失败"));card.Refresh();dirty=false;RefreshStats();}
        catch(Exception ex){Say(ex.Message);return;}finally{SetEditing(false);}
        await NextReviewAsync();
    }
    private void BackToOverview(){editorGeneration++;previewGeneration++;dirty=false;Surface.Clear();PreviewImage.Source=null;current=null;EditorPanel.Visibility=Visibility.Collapsed;OverviewPanel.Visibility=Visibility.Visible;BackButton.Visibility=Visibility.Collapsed;ApplyFilter();}
    private void Back_Click(object sender,RoutedEventArgs e){if(Available()&&DiscardEdits())BackToOverview();}
    private void Fit_Click(object sender,RoutedEventArgs e)=>Surface.Fit();
    private async void Window_KeyDown(object sender,KeyEventArgs e)
    {
        if(!Available()||EditorPanel.Visibility!=Visibility.Visible||e.OriginalSource is TextBox||e.IsRepeat)return;
        if(e.Key==Key.Enter){e.Handled=true;await SaveNextAsync();}
        if(e.Key==Key.F){Surface.Fit();e.Handled=true;}
        if(e.Key==Key.Z&&Keyboard.Modifiers.HasFlag(ModifierKeys.Control)){Surface.Undo();e.Handled=true;}
    }
    private void Window_Closing(object? sender,CancelEventArgs e)
    {
        if(engine?.IsRunning==true){e.Cancel=true;closingRequested=true;engine.RequestStop();Say("完成当前照片并保存进度后关闭…");return;}
        if(editing){e.Cancel=true;Say("请等待当前操作完成后关闭。");return;}
        if(!DiscardEdits())e.Cancel=true;
    }
    internal async Task VerifyWorkflowAsync(string report)
    {
        if(engine is null)throw new InvalidOperationException("UI verification needs a synthetic fixture batch.");
        var checks=new List<string>();
        string orientedFile=Path.Combine(Path.GetDirectoryName(engine.Batch.Source)!,"orientation.jpg");
        if(new ThumbConverter().Convert(orientedFile+"|exif-check",typeof(BitmapSource),null!,CultureInfo.InvariantCulture) is not BitmapSource oriented||oriented.PixelWidth>=oriented.PixelHeight)throw new Exception("EXIF thumbnail orientation mismatch");checks.Add("EXIF thumbnail orientation");
        FilterBox.SelectedIndex=1;ApplyFilter();
        if(filtered.Count!=cards.Count(c=>c.State==PhotoState.NeedsReview))throw new Exception("review filter mismatch");checks.Add("review filter");
        var review=filtered.First(c=>c.Record.Corners?.Length==4);await OpenPhotoAsync(review);
        if(Surface.Points.Count!=4||PreviewImage.Source is null)throw new Exception("editor preview missing");checks.Add("corners and preview");
        Surface.Fit();await SaveNextAsync();
        if(review.State!=PhotoState.Confirmed||!File.Exists(engine.OutputPath(review.Record)))throw new Exception("UI save missing");checks.Add("confirm and next");
        BackToOverview();FilterBox.SelectedIndex=0;SearchBox.Text="does-not-exist-193742";ApplyFilter();
        if(filtered.Count!=0)throw new Exception("search mismatch");checks.Add("filename search");SearchBox.Text="";ApplyFilter();
        Store.WriteJson(report,new{checks,passed=checks.Count});
    }
    private static BitmapSource ToBitmap(Mat mat)
    {
        int stride=mat.Width*3;var bytes=new byte[stride*mat.Height];for(int y=0,rows=mat.Rows;y<rows;y++)System.Runtime.InteropServices.Marshal.Copy(mat.Ptr(y),bytes,y*stride,stride);
        var bitmap=BitmapSource.Create(mat.Width,mat.Height,96,96,PixelFormats.Bgr24,null,bytes,stride);bitmap.Freeze();return bitmap;
    }
}
