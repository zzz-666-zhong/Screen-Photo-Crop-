using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Threading;

namespace Crop.Desktop;
public partial class App : Application
{
    protected override async void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);
        DispatcherUnhandledException += (_, args) =>
        {
            AppDialog.Error(MainWindow, args.Exception.Message);
            args.Handled = true;
        };
        int capture=Array.IndexOf(e.Args,"--screenshot");
        string? testPreferences = capture >= 0 && capture + 1 < e.Args.Length
            ? Path.Combine(Path.GetDirectoryName(Path.GetFullPath(e.Args[capture + 1]))!, ".test-preferences.json")
            : null;
        var window=new MainWindow(testPreferences);MainWindow=window;
        if (capture >= 0)
        {
            window.Left = -12000;
            window.Top = 0;
            window.ShowInTaskbar = false;
            window.WindowStartupLocation = WindowStartupLocation.Manual;
            if (e.Args.Contains("--minimum-size"))
            {
                window.Width = window.MinWidth;
                window.Height = window.MinHeight;
            }
        }
        window.Show();
        int open=Array.IndexOf(e.Args,"--open");
        if(open>=0&&open+1<e.Args.Length)await window.OpenBatchAsync(e.Args[open+1]);
        if(capture>=0&&capture+1<e.Args.Length)
        {
            try
            {
                int verify=Array.IndexOf(e.Args,"--verify-ui");
                if(verify>=0&&verify+1<e.Args.Length)await window.VerifyWorkflowAsync(e.Args[verify+1]);
                int paging = Array.IndexOf(e.Args, "--verify-pagination");
                if (paging >= 0 && paging + 1 < e.Args.Length) window.VerifyPagination(e.Args[paging + 1]);
                if(e.Args.Contains("--edit-first"))await window.OpenFirstAsync();
                await Task.Delay(600);await Dispatcher.InvokeAsync(()=>{},DispatcherPriority.ApplicationIdle);
                window.UpdateLayout();
                var visual=(FrameworkElement)window.Content; var bitmap=new RenderTargetBitmap((int)visual.ActualWidth,(int)visual.ActualHeight,96,96,PixelFormats.Pbgra32);bitmap.Render(visual);
                var encoder=new PngBitmapEncoder();encoder.Frames.Add(BitmapFrame.Create(bitmap));
                using(var stream=File.Create(e.Args[capture+1]))encoder.Save(stream);
                Shutdown(0);
            }
            catch(Exception ex){File.WriteAllText(e.Args[capture+1]+".error.txt",ex.ToString());Shutdown(1);}
        }
    }
}
