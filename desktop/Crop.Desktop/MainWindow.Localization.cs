using System.Windows.Controls;
using System.Windows.Markup;

namespace Crop.Desktop;

public partial class MainWindow
{
    private readonly Dictionary<TextBlock, string> localizedText = new();
    private readonly Dictionary<ContentControl, string> localizedCaptions = new();

    private void SetText(TextBlock control, string text)
    {
        localizedText[control] = text;
        control.Text = UiText.Text(text);
    }

    private void SetCaption(ContentControl control, string caption)
    {
        localizedCaptions[control] = caption;
        control.Content = UiText.Text(caption);
    }

    private void ApplyCulture() => Language = XmlLanguage.GetLanguage(UiText.Language);

    private void AppLanguage_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (initialized)
            ChangeLanguage(AppLanguageSelector.SelectedIndex == 1 ? UiText.English : UiText.Chinese);
    }

    private void ChangeLanguage(string code)
    {
        if (code == UiText.Language) return;
        preferences.Language = code;
        UiText.SetLanguage(code);
        ApplyCulture();
        AppLanguageSelector.SelectedIndex = code == UiText.English ? 1 : 0;
        helpWindow?.SelectLanguage(code);
        foreach (var (control, text) in localizedText) control.Text = UiText.Text(text);
        foreach (var (control, caption) in localizedCaptions) control.Content = UiText.Text(caption);
        foreach (var card in cards) card.RefreshLabels();
        if (engine is null && selectedFiles is not null)
            SourceBox.Text = UiText.Text($"{selectedFiles.Length} 张已选照片");
        SavePreferences();
    }
}
