using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows;
using System.Windows.Markup;

namespace Crop.Desktop;

internal static class UiText
{
    private static readonly Dictionary<string, string> Translation = LoadTranslation();
    private static readonly (string Key, Regex Pattern, string Translation, int Arguments)[] Templates = Translation
        .Select(pair => (Pair: pair, Slots: Regex.Matches(pair.Key, @"\{(\d+)\}")))
        .Where(item => item.Slots.Count > 0)
        .OrderByDescending(item => item.Pair.Key.Length)
        .Select(item => (
            item.Pair.Key,
            new Regex("^" + string.Join("(.+?)", Regex.Split(item.Pair.Key, @"\{\d+\}").Select(Regex.Escape)) + "$",
                RegexOptions.CultureInvariant),
            item.Pair.Value,
            item.Slots.Count))
        .ToArray();
    private static readonly string[] Prefixes = Translation.Keys
        .Where(key => key.EndsWith('：') || key.EndsWith(' ') || key.StartsWith("表格待重试。", StringComparison.Ordinal))
        .OrderByDescending(key => key.Length).ToArray();
    private static ResourceDictionary? active;

    public const string Chinese = "zh-CN";
    public const string English = "en-US";
    public static string Language { get; private set; } = Chinese;

    private static Dictionary<string, string> LoadTranslation()
    {
        using var stream = typeof(UiText).Assembly.GetManifestResourceStream("ScreenCrop.UiText.en.json")
            ?? throw new InvalidOperationException("The English UI resources are missing.");
        return JsonSerializer.Deserialize<Dictionary<string, string>>(stream)
            ?? throw new InvalidOperationException("The English UI resources are empty.");
    }

    public static void SetLanguage(string? language)
    {
        language = language == English ? English : Chinese;
        if (active is not null && Language == language) return;
        Language = language;
        var localized = new ResourceDictionary();
        localized.Add("AppLanguage", XmlLanguage.GetLanguage(language));
        foreach (var pair in Translation)
            localized.Add(pair.Key, language == English ? pair.Value : pair.Key);
        var dictionaries = Application.Current.Resources.MergedDictionaries;
        if (active is null) dictionaries.Add(localized);
        else dictionaries[dictionaries.IndexOf(active)] = localized;
        active = localized;
    }

    public static string Text(string value)
    {
        if (Language != English || !value.Any(c => c is >= '\u3400' and <= '\u9FFF')) return value;
        if (Translation.TryGetValue(value, out string? exact)) return exact;

        const string weakBoundary = "边界证据较弱：";
        if (value.StartsWith(weakBoundary, StringComparison.Ordinal))
            return Translation[weakBoundary] + string.Join(", ", value[weakBoundary.Length..].Split('、').Select(Text));
        foreach (string prefix in Prefixes)
        {
            if (!value.StartsWith(prefix, StringComparison.Ordinal)) continue;
            return Translation[prefix] + Text(value[prefix.Length..]);
        }
        foreach (var (key, pattern, translated, arguments) in Templates)
        {
            var match = pattern.Match(value);
            if (!match.Success) continue;
            var values = Enumerable.Range(1, arguments).Select(index => (object)match.Groups[index].Value).ToArray();
            if (key == "已归档 {0} · {1}。可更新拍摄失败表。")
                values[1] = Text((string)values[1]);
            return string.Format(CultureInfo.InvariantCulture, translated, values);
        }
        if (value.Contains('；')) return string.Join("; ", value.Split('；').Select(Text));
        if (value.Contains(" · ", StringComparison.Ordinal)) return string.Join(" · ", value.Split(" · ").Select(Text));
        return value;
    }
}
