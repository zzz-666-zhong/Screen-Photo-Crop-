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
        DispatcherUnhandledException += (_,args) => { MessageBox.Show(args.Exception.Message,"操作未完成",MessageBoxButton.OK,MessageBoxImage.Error);args.Handled=true; };
        var window=new MainWindow();MainWindow=window;
        int capture=Array.IndexOf(e.Args,"--screenshot");
        if(capture>=0){window.Left=-12000;window.Top=0;window.ShowInTaskbar=false;window.WindowStartupLocation=WindowStartupLocation.Manual;}
        window.Show();
        int open=Array.IndexOf(e.Args,"--open");
        if(open>=0&&open+1<e.Args.Length)await window.OpenBatchAsync(e.Args[open+1]);
        if(capture>=0&&capture+1<e.Args.Length)
        {
            try
            {
                int verify=Array.IndexOf(e.Args,"--verify-ui");
                if(verify>=0&&verify+1<e.Args.Length)await window.VerifyWorkflowAsync(e.Args[verify+1]);
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
