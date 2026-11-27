using System.Windows;
using System.Windows.Controls;

namespace Crop.Desktop;

internal static class AppDialog
{
    public static bool Confirm(Window owner, string message, string title, string action, bool preferCancel = false) =>
        Show(owner, message, title, action, allowCancel: true, preferCancel);

    public static void Error(Window? owner, string message) =>
        Show(owner, message, "操作未完成", "确定", allowCancel: false, preferCancel: false);

    private static bool Show(Window? owner, string message, string title, string action, bool allowCancel, bool preferCancel)
    {
        var dialog = new Window
        {
            Title = UiText.Text(title), Width = 475, MaxHeight = 480, SizeToContent = SizeToContent.Height,
            ResizeMode = ResizeMode.NoResize, ShowInTaskbar = false,
            WindowStartupLocation = owner?.IsVisible == true ? WindowStartupLocation.CenterOwner : WindowStartupLocation.CenterScreen,
            Style = (Style)Application.Current.FindResource("WindowTypography")
        };
        if (owner?.IsVisible == true) dialog.Owner = owner;
        var layout = new DockPanel { Margin = new Thickness(17) };
        var buttons = new StackPanel { Orientation = Orientation.Horizontal, HorizontalAlignment = HorizontalAlignment.Right,
            Margin = new Thickness(0, 15, 0, 0) };
        DockPanel.SetDock(buttons, Dock.Bottom);
        layout.Children.Add(buttons);

        if (allowCancel)
            buttons.Children.Add(new Button { Content = UiText.Text("取消"), IsCancel = true, IsDefault = preferCancel,
                Margin = new Thickness(0, 0, 8, 0), MinWidth = 78 });
        var confirm = new Button { Content = UiText.Text(action), IsDefault = !preferCancel, IsCancel = !allowCancel, MinWidth = 78,
            Style = (Style)Application.Current.FindResource("Primary") };
        confirm.Click += (_, _) => dialog.DialogResult = true;
        buttons.Children.Add(confirm);
        layout.Children.Add(new ScrollViewer
        {
            VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            Content = new TextBlock { Text = UiText.Text(message), TextWrapping = TextWrapping.Wrap }
        });
        dialog.Content = layout;
        return dialog.ShowDialog() == true;
    }
}
