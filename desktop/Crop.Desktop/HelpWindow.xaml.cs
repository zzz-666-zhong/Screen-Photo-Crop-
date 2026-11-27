using System.Text.Json;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Markup;

namespace Crop.Desktop;

public partial class HelpWindow : Window
{
    private sealed record GuideStep(string Heading, string Body);
    private sealed record GuideTopic(string Id, string Title, GuideStep[] Steps);
    private sealed record GuideEdition(string Title, string ContentsLabel, GuideTopic[] Topics);

    private static readonly Lazy<Dictionary<string, GuideEdition>> Editions = new(LoadEditions);
    internal event Action<string>? LanguageRequested;

    public HelpWindow(string initialTopic)
    {
        InitializeComponent();
        SelectLanguage(UiText.Language);
        SelectTopic(initialTopic);
    }

    private static Dictionary<string, GuideEdition> LoadEditions()
    {
        using var stream = typeof(HelpWindow).Assembly.GetManifestResourceStream("ScreenCrop.UserGuide.json")
            ?? throw new InvalidOperationException("The built-in user guide is missing.");
        return JsonSerializer.Deserialize<Dictionary<string, GuideEdition>>(stream, new JsonSerializerOptions(JsonSerializerDefaults.Web))
            ?? throw new InvalidOperationException("The built-in user guide is empty.");
    }

    private void Language_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (LanguageSelector.SelectedItem is not ComboBoxItem { Tag: string code }) return;
        string topicId = (TopicList.SelectedItem as GuideTopic)?.Id ?? "start";
        var edition = Editions.Value[code];
        Language = XmlLanguage.GetLanguage(code);
        Title = $"ScreenCrop · {edition.Title}";
        GuideTitle.Text = edition.Title;
        AutomationProperties.SetName(TopicList, edition.ContentsLabel);
        TopicList.ItemsSource = edition.Topics;
        SelectTopic(topicId);
        LanguageRequested?.Invoke(code);
    }

    internal void SelectLanguage(string code) => LanguageSelector.SelectedIndex = code == UiText.English ? 1 : 0;

    private void SelectTopic(string id)
    {
        TopicList.SelectedItem = TopicList.Items.OfType<GuideTopic>().FirstOrDefault(topic => topic.Id == id)
            ?? TopicList.Items.OfType<GuideTopic>().First();
    }

    private void Topic_Changed(object sender, SelectionChangedEventArgs e)
    {
        if (TopicList.SelectedItem is not GuideTopic topic) return;
        TopicTitle.Text = topic.Title;
        Instructions.ItemsSource = topic.Steps;
        ReadingPane.ScrollToTop();
    }

    private void Help_PreviewKeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key != Key.Escape || LanguageSelector.IsDropDownOpen) return;
        e.Handled = true;
        Close();
    }
}
