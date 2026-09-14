"""Internationalization support (English / Turkish).

The UI language and the results language are configured independently.
UI-facing strings resolve through ``t()``, results-facing strings through ``tr()``.
"""

LANGUAGES = {
    "en": "English",
    "tr": "Türkçe",
}

TRANSLATIONS = {
    "en": {
        "app_title": "Folder Scanner",
        "folders": "Folders",
        "add": "Add",
        "remove": "Remove",
        "select_folder": "Select folder",
        "settings": "Settings",
        "search_text": "Search text",
        "match_method": "Match method",
        "exact": "Exact Match",
        "fuzzy": "Fuzzy Match",
        "threshold": "Fuzzy threshold",
        "file_types": "File types",
        "ft_filename": "File Name",
        "ft_word": "Word",
        "ft_excel": "Excel",
        "ft_pdf": "PDF",
        "ft_txt": "TXT",
        "ui_language": "Interface language",
        "result_language": "Results language",
        "start": "Start Search",
        "stop": "Stop",
        "results": "Results",
        "col_folder": "Folder",
        "col_file": "File",
        "col_count": "Match count",
        "col_locations": "Locations",
        "scanning": "Searching…",
        "done": "Search finished ({count} file(s), {matches} matches)",
        "no_files": "No files to scan. Check some folders and file types.",
        "no_results": "No results",
        "empty_query": "Enter a search text.",
        "select_folder_first": "Select at least one folder to add.",
        "confirm_remove": "Remove selected folder(s) from the list?",
        "page": "Page",
        "line": "Line",
        "cell": "Cell",
        "para": "Para",
        "file_name": "In file name",
        "open_error": "Could not open file: {path}",
        "more": "+{n} more",
        "canceled": "Search canceled.",
        "video_unavailable": "Video unavailable",
        "close_button": "Close",
        "search_placeholder": "Enter text to search…",
    },
    "tr": {
        "app_title": "Klasör Tarayıcı",
        "folders": "Klasörler",
        "add": "Ekle",
        "remove": "Kaldır",
        "select_folder": "Klasör seç",
        "settings": "Ayarlar",
        "search_text": "Aranacak metin",
        "match_method": "Eşleşme yöntemi",
        "exact": "Birebir Eşleşme",
        "fuzzy": "Bulanık Eşleşme",
        "threshold": "Bulanık eşik",
        "file_types": "Dosya türleri",
        "ft_filename": "Dosya Adı",
        "ft_word": "Word",
        "ft_excel": "Excel",
        "ft_pdf": "PDF",
        "ft_txt": "TXT",
        "ui_language": "Arayüz dili",
        "result_language": "Sonuç dili",
        "start": "Aramayı Başlat",
        "stop": "Durdur",
        "results": "Sonuçlar",
        "col_folder": "Klasör",
        "col_file": "Dosya",
        "col_count": "Eşleşme Sayısı",
        "col_locations": "Bulunduğu Yerler",
        "scanning": "Aranıyor…",
        "done": "Arama tamamlandı ({count} dosya, {matches} eşleşme)",
        "no_files": "Taranacak dosya yok. Klasörleri ve dosya türlerini işaretleyin.",
        "no_results": "Sonuç yok",
        "empty_query": "Aranacak metin girin.",
        "select_folder_first": "Eklenecek en az bir klasör seçin.",
        "confirm_remove": "Seçili klasörler listeden kaldırılsın mı?",
        "page": "Sayfa",
        "line": "Satır",
        "cell": "Hücre",
        "para": "Paragraf",
        "file_name": "Dosya adında",
        "open_error": "Dosya açılamadı: {path}",
        "more": "+{n} daha",
        "canceled": "Arama iptal edildi.",
        "video_unavailable": "Video kullanılamıyor",
        "close_button": "Kapat",
        "search_placeholder": "Aranacak metni girin…",
    },
}


class I18n:
    """Resolves translated strings for the single application language.

    There is no separate "results language": outputs use the same language as
    the interface. ``tr()`` is kept as an alias for clarity where output text
    is produced.
    """

    def __init__(self, ui_language: str = "en"):
        self._ui = ui_language if ui_language in LANGUAGES else "en"

    @property
    def ui_language(self) -> str:
        return self._ui

    @ui_language.setter
    def ui_language(self, value: str) -> None:
        if value in LANGUAGES:
            self._ui = value

    def _get(self, key: str) -> str:
        table = TRANSLATIONS.get(self._ui, TRANSLATIONS["en"])
        return table.get(key, TRANSLATIONS["en"].get(key, key))

    def t(self, key: str, **kwargs) -> str:
        """Resolve a UI string in the application language."""
        return self._format(self._get(key), kwargs)

    def tr(self, key: str, **kwargs) -> str:
        """Alias of ``t()``; results/headers use the application language."""
        return self.t(key, **kwargs)

    @staticmethod
    def _format(template: str, kwargs) -> str:
        if not kwargs:
            return template
        return template.format(**kwargs)