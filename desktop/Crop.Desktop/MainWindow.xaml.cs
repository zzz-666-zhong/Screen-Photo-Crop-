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
    public PhotoState State => Record.Error != PhotoError.None && (Record.PendingWrite is not null || Record.PendingRemoval is not null)
        ? PhotoState.Error : Record.State;
    public string Reason => string.Join(" · ",Record.Reasons);
    public string StatusText => State switch { PhotoState.Pending=>"未处理",PhotoState.Processing=>"定位中…",PhotoState.AutoAccepted=>"自动通过",PhotoState.NeedsReview=>"待复核",PhotoState.Confirmed=>"人工确认",PhotoState.Rejected=>"拍摄失败",_=>"处理错误" };
    public bool HasCropPreview => Record.Output is not null &&
        Record.State is PhotoState.AutoAccepted or PhotoState.Confirmed or PhotoState.NeedsReview;
    public bool CanBulkConfirm => Record.Corners?.Length == 4 &&
        Record.State is PhotoState.AutoAccepted or PhotoState.NeedsReview;
    public string ThumbnailPath => (engine.OutputPath(Record) is string output && File.Exists(output)?output:engine.SourcePath(Record))+"|"+(Record.UpdatedAt?.Ticks??0);
    public string BoundaryKey => engine.SourcePath(Record)+"|"+(Record.UpdatedAt?.Ticks??0)+"|"+Record.Width+"|"+Record.Height+"|"+string.Join(';',(State==PhotoState.Rejected?[]:Record.Corners??[]).Select(p=>p.X.ToString(CultureInfo.InvariantCulture)+","+p.Y.ToString(CultureInfo.InvariantCulture)));
    private bool selected;
    public bool Selected {get=>selected;set {selected=value;Changed(nameof(Selected));}}
    public event PropertyChangedEventHandler? PropertyChanged;
    private void Changed(string property)=>PropertyChanged?.Invoke(this,new(property));
    public void Refresh()
    {
        if (!CanBulkConfirm && Selected) Selected = false;
        Changed(nameof(State));Changed(nameof(StatusText));Changed(nameof(Reason));
        Changed(nameof(ThumbnailPath));Changed(nameof(BoundaryKey));Changed(nameof(HasCropPreview));Changed(nameof(CanBulkConfirm));
    }
}
public sealed class StateBrushConverter : IValueConverter
{
    public object Convert(object value,Type type,object parameter,CultureInfo culture)=>new SolidColorBrush((System.Windows.Media.Color)System.Windows.Media.ColorConverter.ConvertFromString(value is PhotoState.NeedsReview?"#976129":value is PhotoState.Error or PhotoState.Rejected?"#9C4435":value is PhotoState.AutoAccepted or PhotoState.Confirmed?"#52694A":"#626A60"));
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
    private List<PhotoCard> cards = [], filtered = [], reviewQueue = [];
    private readonly Dictionary<PhotoCard, PhotoState> counted = new();
    private readonly int[] stateCounts = new int[Enum.GetValues<PhotoState>().Length];
    private readonly HashSet<int> progressCards = [];
    private readonly HashSet<PhotoCard> retryable = [];
    private readonly Stopwatch timer = new();
    private readonly System.Windows.Threading.DispatcherTimer progressTimer;
    private BatchProgress? lastProgress;
    private PhotoCard? current;
    private string[]? selectedFiles;
    private AppPreferences preferences = new();
    private CropOptions setupOptions = new();
    private Mat? previewSource;
    private CancellationTokenSource? previewRequest;
    private int originalWidth, originalHeight, candidateIndex, page;
    private int shownPage = -1, shownPageCount = -1;
    private string? originalHash;
    private PixelPoint[][] candidates = [];
    private bool initialized, editing, dirty, closingRequested, restoringFilter, syncingPage;
    private const int PageSize = 12;
    private int PageCount => filtered.Count == 0 ? 0 : 1 + (filtered.Count - 1) / PageSize;
    private readonly string preferencesPath;

    private sealed class AppPreferences
    {
        public string Source { get; set; } = "";
        public string Output { get; set; } = "";
        public CropOptions Options { get; set; } = new();
        public int AuditPercent { get; set; } = 10;
        public Dictionary<string, ReviewBookmark> Batches { get; set; } = [];
    }
    private sealed record ReviewBookmark(int Filter, string Search, string? Photo);
    private sealed record EditorImage(Mat Pixels, BitmapSource Bitmap, int Width, int Height, string Hash);

    public MainWindow(string? isolatedPreferencesPath = null)
    {
        preferencesPath = isolatedPreferencesPath ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "ScreenCrop", "preferences.json");
        InitializeComponent();
        progressTimer = new System.Windows.Threading.DispatcherTimer { Interval = TimeSpan.FromMilliseconds(150) };
        progressTimer.Tick += (_, _) => FlushProgress();
        Surface.PointsChanged += Surface_Changed;
        PreviewKeyDown += Window_KeyDown;
        try
        {
            if (File.Exists(preferencesPath))
                preferences = System.Text.Json.JsonSerializer.Deserialize<AppPreferences>(File.ReadAllText(preferencesPath), Store.Json) ?? new();
        }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException or System.Text.Json.JsonException) { }
        SourceBox.Text = preferences.Source;
        OutputBox.Text = preferences.Output;
        ApplyOptions(preferences.Options);
        initialized = true;
        ApplyFilter();
    }

    private void SetEditing(bool value)
    {
        editing = value;
        EditorPanel.IsEnabled = !value;
        RefreshActions();
    }
    private void Say(string message) => StatusLine.Text = message;
    private bool Available() => !(engine?.IsRunning ?? false) && !editing;
    private int Count(PhotoState state) => stateCounts[(int)state];

    private void RefreshActions()
    {
        if (!initialized) return;
        bool available = Available();
        ExportFailuresButton.IsEnabled = available && engine is not null;
        MarkCaptureFailedButton.IsEnabled = available && current is not null && CaptureReasonBox.SelectedIndex > 0;
        RunButton.IsEnabled = available && (engine is null || Count(PhotoState.Pending) > 0);
        RetryButton.IsEnabled = available && retryable.Count > 0;
        SelectPageButton.IsEnabled = available && filtered.Count > 0;
        AcceptSelectedButton.IsEnabled = available && engine is not null;
        ResumeReviewButton.Visibility = Bookmark()?.Photo is not null ? Visibility.Visible : Visibility.Collapsed;
        ResumeReviewButton.IsEnabled = available;
        CandidateButton.IsEnabled = available && candidates.Length > 1;
        int index = current is null ? -1 : reviewQueue.IndexOf(current);
        PreviousReviewButton.IsEnabled = available && index > 0;
        NextReviewButton.IsEnabled = available && index >= 0 && index + 1 < reviewQueue.Count;
    }

    private void ShowEditor(bool visible)
    {
        EditorPanel.Visibility = visible ? Visibility.Visible : Visibility.Collapsed;
        StatsPanel.Visibility = FilterPanel.Visibility = OverviewPanel.Visibility =
            visible ? Visibility.Collapsed : Visibility.Visible;
        BackButton.Visibility = visible ? Visibility.Visible : Visibility.Collapsed;
        RunButton.Visibility = visible ? Visibility.Collapsed : Visibility.Visible;
        WorkspaceTitle.Text = visible ? "照片复核" : "批量裁剪";
        Subtitle.Text = engine is null ? "选择照片目录，或打开已有批次" :
            visible ? $"第 {Math.Max(1, reviewQueue.IndexOf(current!) + 1)} 张 / 共 {Math.Max(1, reviewQueue.Count)} 张" :
            $"{Path.GetFileName(engine.Batch.Source)}  /  {engine.Batch.Photos.Count} 张照片";
    }

    private void EditorPanel_SizeChanged(object sender, SizeChangedEventArgs e)
    {
        if (initialized && e.HeightChanged) PreviewFrame.Height = Math.Clamp(e.NewSize.Height - 363, 100, 208);
    }

    private void RefreshCard(PhotoCard card)
    {
        if (counted.TryGetValue(card, out var previous)) stateCounts[(int)previous]--;
        counted[card] = card.State;
        stateCounts[(int)card.State]++;
        if (engine?.CanRetry(card.Record) == true) retryable.Add(card);
        else retryable.Remove(card);
        card.Refresh();
    }

    private void RefreshStats()
    {
        TotalText.Text = engine is null ? "—" : cards.Count.ToString();
        AutoText.Text = Count(PhotoState.AutoAccepted).ToString();
        ManualText.Text = Count(PhotoState.Confirmed).ToString();
        ReviewText.Text = Count(PhotoState.NeedsReview).ToString();
        CaptureFailedText.Text = Count(PhotoState.Rejected).ToString();
        ErrorText.Text = Count(PhotoState.Error).ToString();
        Progress.Value = cards.Count == 0 ? 0 :
            (cards.Count - Count(PhotoState.Pending) - Count(PhotoState.Processing)) * 100d / cards.Count;
        RefreshActions();
    }

    private void Attach(BatchEngine batch)
    {
        ReleasePreview();
        engine = batch;
        cards = batch.Batch.Photos.Select(p => new PhotoCard(batch, p)).ToList();
        counted.Clear();
        retryable.Clear();
        Array.Clear(stateCounts);
        foreach (var card in cards) RefreshCard(card);
        page = 0;
        current = null;
        reviewQueue = [];
        SourceBox.Text = batch.Batch.Source;
        OutputBox.Text = batch.Batch.Destination;
        ApplyOptions(batch.Batch.Options);
        SetupPanel.IsEnabled = false;
        LockedHint.Visibility = Visibility.Visible;
        ResultsButton.IsEnabled = true;
        RunButton.Content = "继续处理";
        ShowEditor(false);
        restoringFilter = true;
        try
        {
            var bookmark = Bookmark();
            FilterBox.SelectedIndex = Math.Clamp(bookmark?.Filter ?? 0, 0, FilterBox.Items.Count - 1);
            SearchBox.Text = bookmark?.Search ?? "";
        }
        finally { restoringFilter = false; }
        RefreshStats();
        ApplyFilter(resetPageInput: true);
        UpdateReportStatus();
    }

    private ReviewBookmark? Bookmark() => engine is null ? null :
        preferences.Batches.GetValueOrDefault(engine.Batch.CreatedAt.ToString("O", CultureInfo.InvariantCulture));

    private void SavePreferences(string? photo = null)
    {
        if (!initialized || restoringFilter) return;
        if (engine is not null)
            preferences.Batches[engine.Batch.CreatedAt.ToString("O", CultureInfo.InvariantCulture)] =
                new ReviewBookmark(FilterBox.SelectedIndex, SearchBox.Text.Trim(), photo ?? Bookmark()?.Photo);
        while (preferences.Batches.Count > 24) preferences.Batches.Remove(preferences.Batches.Keys.First());
        try { Store.WriteJson(preferencesPath, preferences); }
        catch (Exception ex) when (ex is IOException or UnauthorizedAccessException) { Say("无法保存本机设置：" + ex.Message); }
    }

    private void ApplyFilter(bool resetPageInput = false)
    {
        if (!initialized) return;
        string query = SearchBox.Text.Trim();
        int filter = FilterBox.SelectedIndex;
        filtered = cards.Where(c => c.Record.RelativePath.Contains(query, StringComparison.OrdinalIgnoreCase))
            .Where(c => filter switch
            {
                1 => c.State == PhotoState.NeedsReview, 2 => c.State == PhotoState.AutoAccepted,
                3 => c.State == PhotoState.Confirmed, 4 => c.State == PhotoState.Error || c.Record.PendingWrite is not null,
                5 => c.State is PhotoState.Pending or PhotoState.Processing, 6 => c.State == PhotoState.Rejected,
                7 => c.State is PhotoState.AutoAccepted or PhotoState.Confirmed, _ => true
            }).ToList();
        RenderPage(resetPageInput);
        PageInfo.Text = engine is null ? "尚未导入照片" : $"{filtered.Count} 张照片";
        EmptyPanel.Visibility = filtered.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
        EmptyTitle.Text = engine is null ? "尚未导入照片" : "没有符合筛选的照片";
        EmptyDetail.Text = engine is null ? "拖入照片，或在左侧选择照片与结果目录。" : "可更改状态或文件名筛选。";
        RefreshActions();
    }

    private void RenderPage(bool resetPageInput)
    {
        int count = PageCount;
        page = Math.Clamp(page, 0, Math.Max(0, count - 1));
        int number = count == 0 ? 0 : page + 1;
        var visible = filtered.GetRange(page * PageSize, Math.Min(PageSize, filtered.Count - page * PageSize));
        if (PhotoGrid.ItemsSource is not IEnumerable<PhotoCard> shown || !shown.SequenceEqual(visible))
            PhotoGrid.ItemsSource = visible;
        PrevPageButton.IsEnabled = number > 1;
        NextPageButton.IsEnabled = number < count;
        PageSelector.IsEnabled = JumpPageButton.IsEnabled = count > 1;

        bool pageChanged = number != shownPage;
        bool countChanged = count != shownPageCount;
        if (pageChanged || countChanged || resetPageInput)
        {
            if (pageChanged || countChanged)
                PagePosition.Text = $"第 {number} 页 / 共 {count} 页";
            string? draft = !resetPageInput && !pageChanged && count > 1 && PageSelector.IsKeyboardFocusWithin
                ? PageSelector.Text : null;
            syncingPage = true;
            try
            {
                if (countChanged) PageSelector.ItemsSource = Enumerable.Range(1, count).ToArray();
                PageSelector.SelectedIndex = number - 1;
                PageSelector.Text = draft ?? (number == 0 ? "" : number.ToString(CultureInfo.InvariantCulture));
            }
            finally { syncingPage = false; }
            shownPage = number;
            shownPageCount = count;
        }

        if (pageChanged || resetPageInput)
        {
            PageInputError.Visibility = Visibility.Collapsed;
            PhotoListScroll.ScrollToTop();
        }
    }

    private void StatFilter_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { Tag: string value } && int.TryParse(value, out int filter))
        {
            SearchBox.Clear();
            FilterBox.SelectedIndex = filter;
        }
    }
    private void Filter_Changed(object sender, SelectionChangedEventArgs e) { page = 0; ApplyFilter(resetPageInput: true); SavePreferences(); }
    private void Search_Changed(object sender, TextChangedEventArgs e) { page = 0; ApplyFilter(resetPageInput: true); }
    private void PrevPage_Click(object sender, RoutedEventArgs e) => NavigateToPage(page);
    private void NextPage_Click(object sender, RoutedEventArgs e) => NavigateToPage(page + 2);

    private void NavigateToPage(int number)
    {
        if (number < 1 || number > PageCount) return;
        page = number - 1;
        RenderPage(resetPageInput: true);
    }

    private void PageSelector_SelectionChanged(object sender, SelectionChangedEventArgs e)
    {
        if (initialized && !syncingPage && PageSelector.SelectedItem is int number)
            NavigateToPage(number);
    }

    private void PageSelector_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key != Key.Enter || PageSelector.IsDropDownOpen) return;
        e.Handled = true;
        JumpToTypedPage();
    }

    private void JumpPage_Click(object sender, RoutedEventArgs e) => JumpToTypedPage();

    private void JumpToTypedPage()
    {
        if (PageCount == 0) return;
        if (int.TryParse(PageSelector.Text.Trim(), NumberStyles.None, CultureInfo.InvariantCulture, out int number) &&
            number >= 1 && number <= PageCount)
        {
            NavigateToPage(number);
            return;
        }
        PageInputError.Text = $"请输入 1–{PageCount} 的页码。";
        PageInputError.Visibility = Visibility.Visible;
    }
    private static string? Folder(string title)
    {
        var dialog = new OpenFolderDialog { Title = title, Multiselect = false };
        return dialog.ShowDialog() == true ? dialog.FolderName : null;
    }

    private void Source_Click(object sender, RoutedEventArgs e)
    {
        string? directory = Folder("选择原照片目录");
        if (directory is not null) SetSource(directory, null);
    }
    private void Files_Click(object sender, RoutedEventArgs e)
    {
        var dialog = new OpenFileDialog { Title = "选择要裁剪的照片", Multiselect = true,
            Filter = "照片|*.jpg;*.jpeg;*.png;*.bmp;*.tif;*.tiff;*.webp" };
        if (dialog.ShowDialog(this) == true) SetSource(Path.GetDirectoryName(dialog.FileName)!, dialog.FileNames);
    }
    private void SetSource(string directory, string[]? files)
    {
        selectedFiles = files;
        SourceBox.IsReadOnly = files is not null;
        SourceBox.Text = files is null ? directory : $"{files.Length} 张已选照片";
        SourceBox.ToolTip = files is null ? directory : string.Join(Environment.NewLine, files.Take(12));
        if (!string.IsNullOrWhiteSpace(directory) && string.IsNullOrWhiteSpace(OutputBox.Text))
            OutputBox.Text = Path.Combine(Path.GetDirectoryName(directory) ?? directory, Path.GetFileName(directory) + "_裁剪结果");
    }
    private void Output_Click(object sender, RoutedEventArgs e)
    {
        if (Folder("选择结果保存位置") is string folder) OutputBox.Text = folder;
    }
    private void Path_Drop(object sender, DragEventArgs e)
    {
        if (!Available() || !SetupPanel.IsEnabled || e.Data.GetData(DataFormats.FileDrop) is not string[] paths || paths.Length == 0) return;
        e.Handled = true;
        if (paths.Length == 1 && Directory.Exists(paths[0])) SetSource(paths[0], null);
        else if (paths.All(path => File.Exists(path) && BatchEngine.IsPhotoFile(path)))
            SetSource(Path.GetDirectoryName(paths[0])!, paths);
        else Say("可拖入一个文件夹，或一组 JPG、PNG、BMP、TIFF、WebP 照片。");
    }

    private bool DiscardEdits() => !dirty || MessageBox.Show(this, "当前四角尚未保存。放弃这次调整？", "未保存的调整",
        MessageBoxButton.YesNo, MessageBoxImage.Question) == MessageBoxResult.Yes;

    private void New_Click(object sender, RoutedEventArgs e)
    {
        if (!Available() || !DiscardEdits()) return;
        SavePreferences();
        ReleasePreview();
        engine = null;
        cards = [];
        filtered = [];
        reviewQueue = [];
        counted.Clear();
        retryable.Clear();
        Array.Clear(stateCounts);
        current = null;
        dirty = false;
        Surface.Clear();
        SetSource(preferences.Source, null);
        OutputBox.Text = preferences.Output;
        ApplyOptions(preferences.Options);
        SetupPanel.IsEnabled = true;
        LockedHint.Visibility = Visibility.Collapsed;
        ResultsButton.IsEnabled = false;
        ExportFailuresButton.Content = "导出拍摄失败表";
        RunButton.Content = "开始整批处理";
        ElapsedText.Text = "";
        ShowEditor(false);
        FilterBox.SelectedIndex = 0;
        SearchBox.Clear();
        RefreshStats();
        ApplyFilter();
        Say("选择新批次的照片与结果目录。");
    }

    private async void Open_Click(object sender, RoutedEventArgs e)
    {
        if (Available() && DiscardEdits() && Folder("打开包含 batch_session.json 的结果目录") is string folder)
            await OpenBatchAsync(folder);
    }

    public async Task OpenBatchAsync(string folder)
    {
        SavePreferences();
        SetEditing(true);
        try
        {
            Attach(await Task.Run(() => BatchEngine.Open(folder)));
            dirty = false;
            Say(engine!.ReportWarning ?? "已打开批次。");
        }
        catch (Exception ex) { Say(ex.Message); }
        finally { SetEditing(false); }
    }

    private async void Run_Click(object sender, RoutedEventArgs e)
    {
        if (!Available() || !DiscardEdits()) return;
        try
        {
            if (engine is null)
            {
                var options = ReadOptions();
                string source = SourceBox.Text.Trim(), destination = OutputBox.Text.Trim();
                if (string.IsNullOrWhiteSpace(destination) || (selectedFiles is null && string.IsNullOrWhiteSpace(source)))
                    throw new ArgumentException("请先选择原照片和结果目录。");
                var files = selectedFiles;
                SetEditing(true);
                var batch = await Task.Run(() => files is null ? BatchEngine.Create(source, destination, options) :
                    BatchEngine.CreateFiles(files, destination, options));
                Attach(batch);
                preferences.Source = batch.Batch.Source;
                preferences.Output = batch.Batch.Destination;
                preferences.Options = options;
                SavePreferences();
                SetEditing(false);
            }
            var active = engine!;
            if (Count(PhotoState.Pending) == 0) { Say("没有未处理照片。可筛选待复核或开始新批次。"); return; }
            dirty = false;
            ReleasePreview();
            current = null;
            ShowEditor(false);
            RunButton.Visibility = Visibility.Collapsed;
            PauseButton.Visibility = Visibility.Visible;
            timer.Restart();
            var progress = new Progress<BatchProgress>(update =>
            {
                if (engine != active) return;
                progressCards.Add(update.Index - 1);
                lastProgress = update;
                if (!progressTimer.IsEnabled) progressTimer.Start();
            });
            Task run = active.RunAsync(progress);
            RefreshActions();
            await run;
            progressTimer.Stop();
            FlushProgress();
            timer.Stop();
            int pending = Count(PhotoState.Pending);
            string summary = pending > 0 ? $"已暂停 · 剩余 {pending} 张" : $"整批处理完成 · {Count(PhotoState.NeedsReview)} 张待复核";
            if (active.LastTimings is BatchTimings timings && timings.Photos > 0)
                summary += $" · 解码 {timings.ReadDecode.TotalSeconds:F1}s / 定位 {timings.Detect.TotalSeconds:F1}s / 校正 {timings.Rectify.TotalSeconds:F1}s / 编码 {timings.Encode.TotalSeconds:F1}s / 写入 {timings.Commit.TotalSeconds:F1}s";
            Say(active.ReportWarning is null ? summary : summary + " · " + active.ReportWarning);
        }
        catch (Exception ex) { Say("处理未完成：" + ex.Message); }
        finally
        {
            progressTimer.Stop();
            FlushProgress();
            SetEditing(false);
            RunButton.Visibility = EditorPanel.Visibility == Visibility.Visible ? Visibility.Collapsed : Visibility.Visible;
            PauseButton.Visibility = Visibility.Collapsed;
            PauseButton.IsEnabled = true;
            if (closingRequested) Close();
        }
    }

    private void FlushProgress()
    {
        if (progressCards.Count == 0) { progressTimer.Stop(); return; }
        foreach (int index in progressCards) if ((uint)index < cards.Count) RefreshCard(cards[index]);
        progressCards.Clear();
        RefreshStats();
        ApplyFilter();
        if (lastProgress is BatchProgress last && engine?.IsRunning == true)
            Say($"{last.Index} / {last.Total} · {last.Photo.RelativePath} · {cards[last.Index - 1].StatusText}");
        ElapsedText.Text = "已用 " + timer.Elapsed.ToString(@"mm\:ss", CultureInfo.InvariantCulture);
    }

    private async void Retry_Click(object sender, RoutedEventArgs e)
    {
        if (engine is null || !Available()) return;
        SetEditing(true);
        try
        {
            await Task.Run(engine.RetryErrors);
            foreach (var card in cards) RefreshCard(card);
            RefreshStats();
            ApplyFilter();
        }
        catch (Exception ex) { Say(ex.Message); return; }
        finally { SetEditing(false); }
        if (Count(PhotoState.Pending) > 0) Run_Click(sender, e);
        else Say(engine.ReportWarning ?? "已检查待恢复的结果。");
    }

    private void Pause_Click(object sender, RoutedEventArgs e)
    {
        engine?.RequestStop();
        PauseButton.IsEnabled = false;
        Say("正在完成当前照片并保存进度，随后暂停。");
    }

    private void Results_Click(object sender, RoutedEventArgs e)
    {
        if (engine is null) return;
        var launch = new ProcessStartInfo("explorer.exe") { UseShellExecute = true };
        launch.ArgumentList.Add(engine.Batch.Destination);
        Process.Start(launch);
    }

    private void SelectPage_Click(object sender, RoutedEventArgs e)
    {
        var visible = filtered.Skip(page * PageSize).Take(PageSize).Where(card => card.CanBulkConfirm).ToList();
        bool select = visible.Any(card => !card.Selected);
        foreach (var card in visible) card.Selected = select;
        Say($"已选择 {cards.Count(card => card.Selected && card.CanBulkConfirm)} 张照片。");
    }

    private async void AcceptSelected_Click(object sender, RoutedEventArgs e)
    {
        if (engine is null || !Available()) return;
        var selected = cards.Where(card => card.Selected && card.CanBulkConfirm).ToList();
        if (selected.Count == 0) { Say("请先勾选已经检查过的照片。"); return; }
        if (MessageBox.Show(this, $"确认保存已勾选的 {selected.Count} 张照片？", "批量确认",
            MessageBoxButton.OKCancel, MessageBoxImage.Question) != MessageBoxResult.OK) return;
        var batch = engine;
        var succeeded = new List<string>();
        var skipped = new List<string>();
        var failed = new List<string>();
        SetEditing(true);
        try
        {
            foreach (var card in selected)
            {
                try
                {
                    if (await AcceptWithConflictAsync(batch, card, card.Record.Corners!, card.Record.Rotation))
                        (card.Record.PendingWrite is null ? succeeded : failed).Add(card.Record.RelativePath);
                    else skipped.Add(card.Record.RelativePath);
                    card.Selected = false;
                    RefreshCard(card);
                }
                catch (BatchChangedException ex)
                {
                    failed.Add(card.Record.RelativePath + " · " + ex.Message);
                    skipped.AddRange(selected.Skip(succeeded.Count + skipped.Count + failed.Count).Select(item => item.Record.RelativePath));
                    break;
                }
                catch (Exception ex) { failed.Add(card.Record.RelativePath + " · " + ex.Message); }
            }
            await Task.Run(batch.RefreshReports);
        }
        catch (Exception ex) { Say(ex.Message); }
        finally
        {
            SetEditing(false);
            RefreshStats();
            ApplyFilter();
            UpdateReportStatus();
        }
        string summary = $"成功 {succeeded.Count} · 跳过 {skipped.Count} · 失败或待恢复 {failed.Count}";
        Say(batch.ReportWarning is null ? summary : summary + " · " + batch.ReportWarning);
        ShowDetails("批量确认结果", new[] { summary, "",
            Block("成功", succeeded), Block("跳过", skipped), Block("失败或待恢复", failed), batch.ReportWarning ?? "" });

        static string Block(string caption, List<string> files) => files.Count == 0 ? caption + " 0 张" :
            caption + " " + files.Count + " 张\n" + string.Join("\n", files);
    }

    private async Task<bool> AcceptWithConflictAsync(BatchEngine batch, PhotoCard card, PixelPoint[] points, int rotation, string? hash = null)
    {
        CropOverwrite? approval = null;
        while (true)
        {
            try
            {
                await Task.Run(() => batch.Accept(card.Record, points, approval, rotation, hash, deferReports: true));
                return true;
            }
            catch (OutputConflictException conflict)
            {
                string file = Path.GetRelativePath(batch.Batch.Destination, conflict.TargetPath);
                if (MessageBox.Show(this, $"「{file}」的内容与上次保存时不同。是否用这次的裁剪结果覆盖？",
                    "确认覆盖导出文件", MessageBoxButton.YesNo, MessageBoxImage.Warning, MessageBoxResult.No) != MessageBoxResult.Yes)
                    return false;
                approval = new CropOverwrite(conflict.TargetPath, conflict.ExistingHash);
            }
        }
    }

    private CropOptions ReadOptions()
    {
        if (!int.TryParse(InsetBox.Text, out int inset) || inset is < 0 or > 100)
            throw new ArgumentException("四边内切需填写 0 到 100 之间的整数。");
        int size = int.Parse(((ComboBoxItem)SizeBox.SelectedItem).Tag.ToString()!, CultureInfo.InvariantCulture);
        return setupOptions with { Square = SquareBox.IsChecked == true, Recursive = RecursiveBox.IsChecked == true,
            OutputSize = size, InsetPixels = inset };
    }

    private void ApplyOptions(CropOptions options)
    {
        setupOptions = options;
        SquareBox.IsChecked = options.Square;
        RecursiveBox.IsChecked = options.Recursive;
        InsetBox.Text = options.InsetPixels.ToString(CultureInfo.InvariantCulture);
        var choice = SizeBox.Items.OfType<ComboBoxItem>().FirstOrDefault(item => item.Tag?.ToString() == options.OutputSize.ToString());
        if (choice is null)
        {
            choice = new ComboBoxItem { Content = $"长边 {options.OutputSize} 像素", Tag = options.OutputSize.ToString() };
            SizeBox.Items.Add(choice);
        }
        SizeBox.SelectedItem = choice;
    }

    private void Advanced_Click(object sender, RoutedEventArgs e)
    {
        try
        {
            var dialog = new OutputSettingsWindow(ReadOptions()) { Owner = this };
            if (dialog.ShowDialog() == true)
            {
                ApplyOptions(dialog.Options);
                preferences.Options = dialog.Options;
                SavePreferences();
            }
        }
        catch (Exception ex) { Say(ex.Message); }
    }

    private async void BatchTools_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not FrameworkElement button || !Available()) return;
        var menu = new ContextMenu { PlacementTarget = button };
        AddMenu(menu, "刷新批次", async () =>
        {
            if (engine is not null && DiscardEdits()) await OpenBatchAsync(engine.Batch.Destination);
        }, engine is not null);
        AddMenu(menu, "重新定位批次", RelocateAsync);
        AddMenu(menu, "导出批次备份 ZIP", BackupAsync, engine is not null);
        AddMenu(menu, "更新批次报表", RefreshReportsAsync, engine is not null);
        AddMenu(menu, "导出拍摄失败历史", () => ExportFailuresAsync(true), engine is not null);
        AddMenu(menu, "批次统计", () => { ShowBatchStats(); return Task.CompletedTask; }, engine is not null);
        foreach (int ratio in new[] { 5, 10, 20 })
            AddMenu(menu, $"抽查自动通过的 {ratio}%", () => AuditAsync(ratio), Count(PhotoState.AutoAccepted) > 0);
        menu.IsOpen = true;
        await Task.CompletedTask;
    }

    private void AddMenu(ContextMenu menu, string label, Func<Task> action, bool enabled = true)
    {
        var item = new MenuItem { Header = label, IsEnabled = enabled };
        item.Click += async (_, _) =>
        {
            try { await action(); }
            catch (Exception ex) { Say(ex.Message); }
        };
        menu.Items.Add(item);
    }

    private async Task RelocateAsync()
    {
        if (!DiscardEdits() || Folder("选择移动后的批次结果目录") is not string destination ||
            Folder("选择对应的原照片目录") is not string source) return;
        SetEditing(true);
        try
        {
            Attach(await Task.Run(() => BatchEngine.Relocate(destination, source)));
            dirty = false;
            Say(engine!.ReportWarning ?? "已核对照片内容并重新定位批次。");
        }
        finally { SetEditing(false); }
    }

    private async Task BackupAsync()
    {
        if (engine is null) return;
        var dialog = new SaveFileDialog { Title = "导出批次备份", Filter = "ZIP 备份|*.zip",
            FileName = $"ScreenCrop-{engine.Batch.CreatedAt:yyyyMMdd-HHmmss}.zip", AddExtension = true, OverwritePrompt = false };
        if (dialog.ShowDialog(this) != true) return;
        var batch = engine;
        SetEditing(true);
        try { await Task.Run(() => batch.ExportBackup(dialog.FileName)); Say("已导出批次备份：" + dialog.FileName); }
        finally { SetEditing(false); }
    }

    private async Task RefreshReportsAsync()
    {
        if (engine is null) return;
        SetEditing(true);
        try
        {
            await Task.Run(engine.RefreshReports);
            UpdateReportStatus();
            Say(engine.ReportWarning ?? "已更新批次报表。");
        }
        finally { SetEditing(false); }
    }

    private void ShowBatchStats()
    {
        if (engine is null) return;
        string[] groups = cards.GroupBy(card => Path.GetDirectoryName(card.Record.RelativePath) ?? "")
            .OrderBy(group => group.Key).Select(group =>
                $"{(group.Key == "" ? "根目录" : group.Key)}  ·  {group.Count()} 张  ·  " +
                $"自动 {group.Count(card => card.State == PhotoState.AutoAccepted)}  人工 {group.Count(card => card.State == PhotoState.Confirmed)}  " +
                $"待复核 {group.Count(card => card.State == PhotoState.NeedsReview)}  " +
                $"拍摄失败 {group.Count(card => card.State == PhotoState.Rejected)}  处理错误 {group.Count(card => card.State == PhotoState.Error)}").ToArray();
        var reasons = cards.Where(card => card.State == PhotoState.Rejected).GroupBy(card => card.Reason)
            .OrderByDescending(group => group.Count()).Select(group => $"{group.Key}  ·  {group.Count()} 张").ToArray();
        ShowDetails("批次统计", new[] { "按拍摄失败原因", reasons.Length == 0 ? "0 张" : string.Join("\n", reasons),
            "", "按子目录", string.Join("\n", groups) });
    }

    private void ShowDetails(string title, IEnumerable<string> lines)
    {
        var content = new TextBlock { Text = string.Join("\n", lines), TextWrapping = TextWrapping.Wrap, Margin = new Thickness(15) };
        var scroll = new ScrollViewer { Content = content, VerticalScrollBarVisibility = ScrollBarVisibility.Auto };
        var dialog = new System.Windows.Window { Title = title, Owner = this, Content = scroll, Width = 640, Height = 445,
            WindowStartupLocation = WindowStartupLocation.CenterOwner, Style = (Style)FindResource("WindowTypography") };
        dialog.ShowDialog();
    }

    private async void Photo_Click(object sender, RoutedEventArgs e)
    {
        if (sender is Button { Tag: PhotoCard card }) await OpenPhotoAsync(card);
    }
    public Task OpenFirstAsync() => cards.Count == 0 ? Task.CompletedTask : OpenPhotoAsync(cards[0]);

    private async void ResumeReview_Click(object sender, RoutedEventArgs e)
    {
        string? photo = Bookmark()?.Photo;
        var card = cards.FirstOrDefault(item => item.Record.RelativePath.Equals(photo, StringComparison.OrdinalIgnoreCase));
        if (card is not null) await OpenPhotoAsync(card);
    }

    private async Task AuditAsync(int percent)
    {
        if (!Available() || !DiscardEdits()) return;
        var accepted = cards.Where(card => card.State == PhotoState.AutoAccepted).ToList();
        int take = (int)Math.Ceiling(accepted.Count * percent / 100d);
        reviewQueue = accepted.OrderBy(card => RiskMargin(card.Record.Evidence))
            .ThenBy(card => card.Record.RelativePath, StringComparer.OrdinalIgnoreCase).Take(take).ToList();
        if (reviewQueue.Count == 0) return;
        await OpenPhotoAsync(reviewQueue[0], preserveQueue: true);
        Say($"抽查 {reviewQueue.Count} 张自动通过照片，优先显示接近通过门槛的结果。");

        static double RiskMargin(FrameEvidence? evidence) => evidence is null ? double.NegativeInfinity :
            Math.Min(Math.Min((evidence.MinSupport - .82) / .18, (evidence.MinContrast - 12) / 18),
                Math.Min((15 - evidence.ExteriorNoise) / 15, (evidence.ScoreGap - .16) / .84));
    }

    private async Task OpenPhotoAsync(PhotoCard card, bool preserveQueue = false)
    {
        if (engine is null || !Available() || !DiscardEdits()) return;
        if (!preserveQueue)
        {
            bool issues = card.State is PhotoState.NeedsReview or PhotoState.Error;
            reviewQueue = issues ? cards.Where(item => item.State is PhotoState.NeedsReview or PhotoState.Error).ToList() :
                filtered.Where(item => item.State == card.State).ToList();
            if (!reviewQueue.Contains(card)) reviewQueue.Insert(0, card);
        }
        var batch = engine;
        ReleasePreview();
        SetEditing(true);
        current = card;
        dirty = false;
        PreviewImage.Source = null;
        Surface.Clear();
        ShowEditor(true);
        EditorName.Text = card.Record.RelativePath;
        CaptureReasonBox.SelectedIndex = 0;
        PreviewInfo.Text = "选满四角后生成预览";
        ReasonText.Text = card.Reason.Length > 0 ? card.Reason : card.State == PhotoState.AutoAccepted
            ? "四边证据满足自动通过规则，可继续检查角点。" : "检查完整图片边界，确认后保存。";
        SaveNextButton.IsEnabled = false;
        SetCandidates(card.Record.Corners, card.Record.Alternatives);
        try
        {
            var editor = await Task.Run(() => ReadEditorImage(batch.SourcePath(card.Record), batch.Batch.Options.PreserveDepth));
            previewSource = editor.Pixels;
            originalWidth = editor.Width;
            originalHeight = editor.Height;
            originalHash = editor.Hash;
            Surface.SetImage(editor.Bitmap, card.Record.Corners, originalWidth, originalHeight, card.Record.Rotation);
            Surface.Focus();
            SaveNextButton.IsEnabled = Surface.Points.Count == 4;
            await PreviewAsync();
        }
        catch (Exception ex)
        {
            PreviewInfo.Text = "无法打开原照片";
            ReasonText.Text = ex.Message;
            Say("打开失败：" + ex.Message);
        }
        finally
        {
            SavePreferences(card.Record.RelativePath);
            SetEditing(false);
        }
    }

    private static EditorImage ReadEditorImage(string path, bool preserveDepth)
    {
        byte[] encoded = File.ReadAllBytes(path);
        string hash = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(encoded)).ToLowerInvariant();
        using var decoded = Store.Decode(encoded, preserveDepth);
        using var display = Store.DisplayPixels(decoded);
        double scale = Math.Min(1, 1600d / Math.Max(decoded.Width, decoded.Height));
        var small = new Mat();
        try
        {
            Cv2.Resize(display, small, new OpenCvSharp.Size(Math.Max(1, (int)Math.Round(scale * display.Width)),
                Math.Max(1, (int)Math.Round(scale * display.Height))), interpolation: InterpolationFlags.Area);
            return new EditorImage(small, ToBitmap(small), decoded.Width, decoded.Height, hash);
        }
        catch { small.Dispose(); throw; }
    }

    private async void Surface_Changed(object? sender, EventArgs e)
    {
        dirty = true;
        SaveNextButton.IsEnabled = Surface.Points.Count == 4;
        if (Surface.Points.Count == 4) await PreviewAsync();
        else
        {
            previewRequest?.Cancel();
            PreviewImage.Source = null;
            PreviewInfo.Text = $"已选 {Surface.Points.Count} / 4 个角点";
        }
    }

    private async Task PreviewAsync()
    {
        if (engine is null || previewSource is null || Surface.Points.Count != 4) return;
        previewRequest?.Cancel();
        var request = new CancellationTokenSource();
        previewRequest = request;
        try
        {
            await Task.Delay(55, request.Token);
            var source = previewSource;
            if (source is null) return;
            double sx = source.Width / (double)originalWidth, sy = source.Height / (double)originalHeight;
            var points = Surface.Points.Select(p => new Point2f((float)(p.X * sx), (float)(p.Y * sy))).ToArray();
            int rotation = Surface.Rotation;
            var options = engine.Batch.Options;
            var previewOptions = options with { InsetPixels = (int)Math.Round(options.InsetPixels * Math.Min(sx, sy)),
                OutputSize = options.OutputSize == 0 ? 0 : Math.Min(options.OutputSize, 900), PreserveDepth = false };
            using var owned = source.Clone();
            var bitmap = await Task.Run(() =>
            {
                request.Token.ThrowIfCancellationRequested();
                using var crop = Store.Rectify(owned, points, previewOptions, rotation);
                request.Token.ThrowIfCancellationRequested();
                return ToBitmap(crop);
            }, request.Token);
            if (previewRequest != request) return;
            PreviewImage.Source = bitmap;
            PreviewInfo.Text = $"预览 {bitmap.PixelWidth} × {bitmap.PixelHeight} · 内切 {options.InsetPixels} px · 旋转 {rotation}°";
            SaveNextButton.IsEnabled = true;
        }
        catch (OperationCanceledException) { }
        catch (Exception ex)
        {
            if (previewRequest == request)
            {
                PreviewImage.Source = null;
                PreviewInfo.Text = ex.Message;
                SaveNextButton.IsEnabled = false;
            }
        }
        finally
        {
            if (previewRequest == request) previewRequest = null;
            request.Dispose();
        }
    }

    private void ReleasePreview()
    {
        previewRequest?.Cancel();
        previewRequest = null;
        previewSource?.Dispose();
        previewSource = null;
        originalHash = null;
    }

    private void SetCandidates(PixelPoint[]? primary, PixelPoint[][]? alternatives)
    {
        candidates = primary is null ? [] : new[] { primary }.Concat(alternatives ?? []).ToArray();
        candidateIndex = 0;
        CandidateInfo.Visibility = candidates.Length > 1 ? Visibility.Visible : Visibility.Collapsed;
        CandidateInfo.Text = $"候选框 1 / {candidates.Length}";
        RefreshActions();
    }

    private async void Detect_Click(object sender, RoutedEventArgs e)
    {
        if (engine is null || current is null || !Available() || previewSource is null) return;
        SetEditing(true);
        try
        {
            using var snapshot = previewSource.Clone();
            double sx = originalWidth / (double)snapshot.Width, sy = originalHeight / (double)snapshot.Height;
            bool square = engine.Batch.Options.Square;
            var result = await Task.Run(() => new FrameDetector().Detect(snapshot, square, mode: DetectionMode.Difficult));
            ReasonText.Text = result.Automatic ? "已重新定位，可检查角点后保存。" : string.Join("；", result.Reasons);
            if (result.Corners is not null)
            {
                PixelPoint[] Map(Point2f[] quad) =>
                    quad.Select(p => new PixelPoint(Math.Clamp(p.X * sx, 0, originalWidth - 1),
                        Math.Clamp(p.Y * sy, 0, originalHeight - 1))).ToArray();
                var primary = Map(result.Corners);
                SetCandidates(primary, result.Alternatives?.Select(Map).ToArray());
                Surface.SetPoints(primary);
                await PreviewAsync();
                Surface.Focus();
            }
        }
        catch (Exception ex) { Say(ex.Message); }
        finally { SetEditing(false); }
    }

    private void Candidate_Click(object sender, RoutedEventArgs e)
    {
        if (candidates.Length <= 1) return;
        candidateIndex = (candidateIndex + 1) % candidates.Length;
        Surface.SetPoints(candidates[candidateIndex]);
        CandidateInfo.Text = $"候选框 {candidateIndex + 1} / {candidates.Length}";
        Surface.Focus();
    }

    private void CornerTools_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not FrameworkElement button || previewSource is null) return;
        var menu = new ContextMenu { PlacementTarget = button };
        void Add(string label, Action action)
        {
            var item = new MenuItem { Header = label };
            item.Click += (_, _) => { action(); Surface.Focus(); };
            menu.Items.Add(item);
        }
        Add("适应窗口", Surface.Fit);
        Add("旋转成图 90°", Surface.Rotate);
        Add("撤销  Ctrl+Z", Surface.Undo);
        Add("重做  Ctrl+Y", Surface.Redo);
        Add("重选当前角点", () => { if (Surface.ReplaceSelected()) Say("点击照片选择新位置，其他角点会保留。"); });
        Add("重选四角", Surface.ResetCorners);
        Add(Surface.Magnifier ? "关闭放大镜" : "打开放大镜", Surface.ToggleMagnifier);
        menu.IsOpen = true;
    }

    private async void SaveNext_Click(object sender, RoutedEventArgs e) => await SaveNextAsync();

    private async Task SaveNextAsync()
    {
        if (engine is null || current is null || !Available() || Surface.Points.Count != 4 || Surface.IsInteracting) return;
        SetEditing(true);
        var card = current;
        var batch = engine;
        bool saved = false;
        try
        {
            saved = await AcceptWithConflictAsync(batch, card, Surface.Points.ToArray(), Surface.Rotation, originalHash);
            if (saved)
            {
                dirty = false;
                RefreshCard(card);
                RefreshStats();
                await Task.Run(batch.RefreshReports);
                UpdateReportStatus();
                Say(batch.ReportWarning is null ? "已确认保存：" + card.Name :
                    (card.Record.PendingWrite is null ? "图片已保存 · " : "结果待落盘 · ") + batch.ReportWarning);
            }
        }
        catch (Exception ex) { Say("保存未完成：" + ex.Message); }
        finally { SetEditing(false); }
        if (saved && card.Record.PendingWrite is null) await NavigateReviewAsync(1);
    }

    private async Task NavigateReviewAsync(int direction)
    {
        if (current is null || !Available() || !DiscardEdits()) return;
        int position = reviewQueue.IndexOf(current) + direction;
        if ((uint)position < (uint)reviewQueue.Count) await OpenPhotoAsync(reviewQueue[position], preserveQueue: true);
        else if (direction > 0)
        {
            BackToOverview();
            Say(engine?.ReportWarning ?? (engine?.FailureReportOutdated() == true ? "复核结束，拍摄失败表需要更新。" : "已到本轮复核末尾。"));
        }
    }

    private async void Skip_Click(object sender, RoutedEventArgs e) => await NavigateReviewAsync(1);
    private async void PreviousReview_Click(object sender, RoutedEventArgs e) => await NavigateReviewAsync(-1);
    private void CaptureReason_Changed(object sender, SelectionChangedEventArgs e) => RefreshActions();
    private async void Reject_Click(object sender, RoutedEventArgs e) => await MarkCaptureFailedAsync();

    private async Task MarkCaptureFailedAsync()
    {
        if (engine is null || current is null || !Available() ||
            CaptureReasonBox.SelectedIndex <= 0 || CaptureReasonBox.SelectedItem is not ComboBoxItem { Content: string reason }) return;
        var batch = engine;
        var card = current;
        SetEditing(true);
        try { await Task.Run(() => batch.Reject(card.Record, reason)); dirty = false; }
        catch (Exception ex) { Say("标记未完成：" + ex.Message); return; }
        finally { RefreshCard(card); RefreshStats(); SetEditing(false); }
        UpdateReportStatus();
        if (card.Record.PendingWrite is null) await NavigateReviewAsync(1);
        Say(batch.ReportWarning ?? $"已归档 {card.Name} · {reason}。可更新拍摄失败表。");
    }

    private void UpdateReportStatus() => ExportFailuresButton.Content =
        engine?.FailureReportOutdated() == true ? "更新拍摄失败表" : "导出拍摄失败表";

    private async void ExportFailures_Click(object sender, RoutedEventArgs e) => await ExportFailuresAsync(false);

    private async Task ExportFailuresAsync(bool history)
    {
        if (engine is null || !Available()) return;
        try
        {
            string report = await SaveFailureReportAsync(history);
            UpdateReportStatus();
            Say("已导出 " + Path.GetFileName(report));
        }
        catch (Exception ex) { Say("导出失败：" + ex.Message); }
    }

    private async Task<string> SaveFailureReportAsync(bool history = false)
    {
        var batch = engine!;
        SetEditing(true);
        try { return await Task.Run(() => batch.ExportCaptureFailures(history)); }
        finally { SetEditing(false); }
    }

    private void BackToOverview()
    {
        ReleasePreview();
        dirty = false;
        Surface.Clear();
        PreviewImage.Source = null;
        current = null;
        candidates = [];
        ShowEditor(false);
        ApplyFilter();
        SavePreferences();
    }

    private void Back_Click(object sender, RoutedEventArgs e)
    {
        if (Available() && DiscardEdits()) BackToOverview();
    }

    private async void Window_KeyDown(object sender, KeyEventArgs e)
    {
        if (!Available() || EditorPanel.Visibility != Visibility.Visible ||
            e.OriginalSource is TextBox or System.Windows.Controls.Primitives.ButtonBase || CaptureReasonBox.IsKeyboardFocusWithin || e.IsRepeat)
            return;
        if (e.Key == Key.Enter) { e.Handled = true; await SaveNextAsync(); }
        if (e.Key == Key.F) { Surface.Fit(); e.Handled = true; }
        if (e.Key == Key.Z && Keyboard.Modifiers.HasFlag(ModifierKeys.Control)) { Surface.Undo(); e.Handled = true; }
        if (e.Key == Key.Y && Keyboard.Modifiers.HasFlag(ModifierKeys.Control)) { Surface.Redo(); e.Handled = true; }
    }

    private void Window_Closing(object? sender, CancelEventArgs e)
    {
        if (engine?.IsRunning == true)
        {
            e.Cancel = true;
            closingRequested = true;
            engine.RequestStop();
            Say("完成当前照片并保存进度后关闭。");
            return;
        }
        if (editing || !DiscardEdits()) { e.Cancel = true; return; }
        if (engine is null)
        {
            try { preferences.Options = ReadOptions(); }
            catch (ArgumentException) { }
        }
        SavePreferences();
        ReleasePreview();
    }

    internal void VerifyPagination(string report)
    {
        if (engine is null || cards.Count <= 2 * PageSize)
            throw new InvalidOperationException("Pagination verification needs at least three pages.");
        var checks = new List<string>();
        FilterBox.SelectedIndex = 0;
        SearchBox.Clear();
        NavigateToPage(1);
        int count = PageCount;
        if (PrevPageButton.IsEnabled || !NextPageButton.IsEnabled ||
            PagePosition.Text != $"第 1 页 / 共 {count} 页" || PageSelector.Items.Count != count)
            throw new InvalidOperationException("Initial page or total page count is incorrect.");
        checks.Add("initial page and total");

        PageSelector.SelectedItem = count;
        var last = ((IEnumerable<PhotoCard>)PhotoGrid.ItemsSource).ToArray();
        if (page != count - 1 || NextPageButton.IsEnabled || !PrevPageButton.IsEnabled ||
            last.Length != filtered.Count - (count - 1) * PageSize || last[0] != filtered[(count - 1) * PageSize])
            throw new InvalidOperationException("Page selection did not display the expected final cards.");
        checks.Add("direct list selection and final page");

        PageSelector.Text = "2";
        JumpPage_Click(JumpPageButton, new RoutedEventArgs());
        if (page != 1 || PagePosition.Text != $"第 2 页 / 共 {count} 页")
            throw new InvalidOperationException("Typed page did not open page two.");
        PageSelector.Text = "1";
        var enter = new KeyEventArgs(Keyboard.PrimaryDevice, PresentationSource.FromVisual(PageSelector),
            Environment.TickCount, Key.Enter) { RoutedEvent = Keyboard.PreviewKeyDownEvent };
        PageSelector.RaiseEvent(enter);
        if (!enter.Handled || page != 0) throw new InvalidOperationException("Enter did not commit the typed page.");
        checks.Add("typed jump and keyboard confirmation");

        PageSelector.Text = (count + 1).ToString(CultureInfo.InvariantCulture);
        JumpToTypedPage();
        if (page != 0 || PageInputError.Visibility != Visibility.Visible)
            throw new InvalidOperationException("An out-of-range page should leave the current page visible.");
        SearchBox.Text = "no-synthetic-photo-82747";
        if (PageCount != 0 || PagePosition.Text != "第 0 页 / 共 0 页" ||
            PageSelector.IsEnabled || JumpPageButton.IsEnabled || NextPageButton.IsEnabled)
            throw new InvalidOperationException("No-match search left page controls enabled.");
        SearchBox.Clear();
        if (page != 0 || PageSelector.Items.Count != count || PageInputError.Visibility != Visibility.Collapsed)
            throw new InvalidOperationException("Restoring the search did not reset pagination.");
        checks.Add("input validation and filtering");
        NavigateToPage(2);
        Store.WriteJson(report, new { checks, passed = checks.Count, page = page + 1, pages = count });
    }

    internal async Task VerifyWorkflowAsync(string report)
    {
        if (engine is null) throw new InvalidOperationException("UI verification needs a synthetic fixture batch.");
        var checks = new List<string>();
        string orientedFile = Path.Combine(Path.GetDirectoryName(engine.Batch.Source)!, "orientation.jpg");
        if (new ThumbConverter().Convert(orientedFile + "|exif-check", typeof(BitmapSource), null!, CultureInfo.InvariantCulture)
            is not BitmapSource oriented || oriented.PixelWidth >= oriented.PixelHeight) throw new Exception("EXIF thumbnail orientation mismatch");
        checks.Add("EXIF thumbnail orientation");

        FilterBox.SelectedIndex = 1;
        ApplyFilter();
        if (filtered.Count != cards.Count(card => card.State == PhotoState.NeedsReview)) throw new Exception("review filter mismatch");
        checks.Add("review filter");

        var review = filtered.First(card => card.Record.Corners?.Length == 4);
        await OpenPhotoAsync(review);
        if (Surface.Points.Count != 4 || PreviewImage.Source is null || previewSource is null) throw new Exception("editor preview missing");
        checks.Add("cached preview and original corners");
        var before = Surface.Points.ToArray();
        Surface.SetPoints(before.Select((point, index) => index == 0 ? point with { X = point.X + 2 } : point));
        Surface.Undo();
        if (!Surface.Points.SequenceEqual(before)) throw new Exception("undo did not restore corners");
        Surface.Redo();
        if (Surface.Points.SequenceEqual(before)) throw new Exception("redo did not restore edit");
        Surface.Undo();
        Surface.Rotate();
        if (Surface.Rotation != 90) throw new Exception("rotation did not change");
        Surface.Undo();
        if (Surface.Rotation != 0) throw new Exception("undo did not restore rotation");
        checks.Add("corner history and rotation");

        dirty = false;
        await SaveNextAsync();
        if (review.State != PhotoState.Confirmed || !File.Exists(engine.OutputPath(review.Record))) throw new Exception("UI save missing");
        checks.Add("confirm and next");
        BackToOverview();
        FilterBox.SelectedIndex = 0;
        SearchBox.Text = "does-not-exist-193742";
        if (filtered.Count != 0) throw new Exception("search mismatch");
        SearchBox.Clear();
        checks.Add("filename search");

        var capture = cards.First(card => card.State == PhotoState.Error);
        await OpenPhotoAsync(capture);
        if (MarkCaptureFailedButton.IsEnabled) throw new Exception("Capture failure reason must be selected");
        CaptureReasonBox.SelectedIndex = 2;
        if (!MarkCaptureFailedButton.IsEnabled) throw new Exception("Capture failure action inaccessible");
        await MarkCaptureFailedAsync();
        if (capture.State != PhotoState.Rejected || capture.Reason != "反光遮挡" || Count(PhotoState.Rejected) == 0)
            throw new Exception("Capture failure reason or count mismatch");
        if (engine.OutputPath(capture.Record) is not string archive || Store.Hash(archive) != Store.Hash(engine.SourcePath(capture.Record)))
            throw new Exception("Original photo was not archived");
        checks.Add("capture failure archive");
        BackToOverview();
        FilterBox.SelectedIndex = 6;
        if (!filtered.Contains(capture) || filtered.Any(card => card.State != PhotoState.Rejected) || !ExportFailuresButton.IsEnabled)
            throw new Exception("Capture failure filter mismatch");
        string csv = File.ReadAllText(await SaveFailureReportAsync());
        if (!csv.Contains(capture.Name) || !csv.Contains("反光遮挡") || !csv.Contains("原照片副本"))
            throw new Exception("Capture failure report is incomplete");
        checks.Add("capture failure filter and report export");
        await OpenPhotoAsync(capture);
        if (Bookmark()?.Photo != capture.Record.RelativePath) throw new Exception("Review bookmark was not saved");
        checks.Add("review bookmark");
        BackToOverview();
        Store.WriteJson(report, new { checks, passed = checks.Count });
    }

    private static BitmapSource ToBitmap(Mat mat)
    {
        int stride = mat.Width * 3;
        int rows = mat.Rows;
        var bytes = new byte[stride * rows];
        for (int y = 0; y < rows; y++)
            System.Runtime.InteropServices.Marshal.Copy(mat.Ptr(y), bytes, y * stride, stride);
        var bitmap = BitmapSource.Create(mat.Width, mat.Height, 96, 96, PixelFormats.Bgr24, null, bytes, stride);
        bitmap.Freeze();
        return bitmap;
    }
}
