import AppKit
import Foundation

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var hwpxURL: URL?
    private var coverURL: URL?
    private var outputURL: URL?
    private var txtURL: URL?
    private var epubURL: URL?

    private let hwpxLabel = NSTextField(labelWithString: "선택되지 않음")
    private let coverLabel = NSTextField(labelWithString: "선택되지 않음")
    private let outputLabel = NSTextField(labelWithString: "HWPX 파일과 같은 폴더")
    private let inputModePopup = NSPopUpButton(frame: .zero, pullsDown: false)
    private let templatePopup = NSPopUpButton(frame: .zero, pullsDown: false)
    private let duplicatePopup = NSPopUpButton(frame: .zero, pullsDown: false)
    private let sourceButton = NSButton(title: "HWPX 선택", target: nil, action: nil)
    private let statusLabel = NSTextField(labelWithString: "HWPX와 표지를 선택해 주세요.")
    private let titleField = NSTextField(string: "")
    private let authorField = NSTextField(string: "")
    private let publisherField = NSTextField(string: "")
    private let dateField = NSTextField(string: "")
    private let uciField = NSTextField(string: "")
    private let submissionEmailField = NSTextField(string: "")
    private let rightsField = NSTextField(string: "")
    private let saveCopyrightButton = NSButton(title: "판권정보 저장하기", target: nil, action: nil)
    private let convertButton = NSButton(title: "TXT + EPUB 만들기", target: nil, action: nil)
    private let openTXTButton = NSButton(title: "TXT 열기", target: nil, action: nil)
    private let openEPUBButton = NSButton(title: "EPUB 열기", target: nil, action: nil)
    private let revealButton = NSButton(title: "결과 폴더 보기", target: nil, action: nil)
    private let spinner = NSProgressIndicator()

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildMainMenu()
        buildWindow()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func buildMainMenu() {
        let mainMenu = NSMenu()

        let appMenuItem = NSMenuItem()
        mainMenu.addItem(appMenuItem)
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "HWPX 전자책 변환기 정보", action: #selector(NSApplication.orderFrontStandardAboutPanel(_:)), keyEquivalent: "")
        appMenu.addItem(withTitle: "오픈소스 라이선스", action: #selector(showLicenses), keyEquivalent: "")
        appMenu.addItem(NSMenuItem.separator())
        appMenu.addItem(withTitle: "HWPX 전자책 변환기 종료", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        appMenuItem.submenu = appMenu

        let editMenuItem = NSMenuItem()
        mainMenu.addItem(editMenuItem)
        let editMenu = NSMenu(title: "편집")
        editMenu.addItem(withTitle: "실행 취소", action: Selector(("undo:")), keyEquivalent: "z")
        editMenu.addItem(withTitle: "다시 실행", action: Selector(("redo:")), keyEquivalent: "Z")
        editMenu.addItem(NSMenuItem.separator())
        editMenu.addItem(withTitle: "오려두기", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "복사", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "붙여넣기", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editMenu.addItem(withTitle: "전체 선택", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
        editMenuItem.submenu = editMenu

        NSApp.mainMenu = mainMenu
    }

    private func buildWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 660, height: 720),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "HWPX → TXT + EPUB"
        window.center()

        let title = NSTextField(labelWithString: "전자책 변환기")
        title.font = .systemFont(ofSize: 24, weight: .bold)
        let subtitle = NSTextField(labelWithString: "HWPX 원고와 표지 이미지로 TXT와 EPUB을 함께 만듭니다.")
        subtitle.textColor = .secondaryLabelColor

        sourceButton.target = self
        sourceButton.action = #selector(selectHWPX)
        sourceButton.bezelStyle = .rounded
        let coverButton = fileButton("표지 선택", #selector(selectCover))
        let outputButton = fileButton("출력 폴더", #selector(selectOutput))
        inputModePopup.addItems(withTitles: ["개별 HWPX", "연재 폴더 일괄"])
        inputModePopup.target = self
        inputModePopup.action = #selector(inputModeChanged)
        templatePopup.addItems(withTitles: ["단행본형", "연재형"])
        templatePopup.target = self
        templatePopup.action = #selector(templateChanged)
        duplicatePopup.addItems(withTitles: ["기존 파일 모두 대치", "기존 파일 건너뛰기"])

        [hwpxLabel, coverLabel, outputLabel].forEach {
            $0.lineBreakMode = .byTruncatingMiddle
            $0.maximumNumberOfLines = 1
        }

        let form = NSGridView(views: [
            [NSTextField(labelWithString: "입력 방식"), inputModePopup],
            [sourceButton, hwpxLabel],
            [coverButton, coverLabel],
            [outputButton, outputLabel],
            [NSTextField(labelWithString: "출력 형식"), templatePopup],
            [NSTextField(labelWithString: "중복 처리"), duplicatePopup],
        ])
        form.rowSpacing = 14
        form.columnSpacing = 14
        form.column(at: 0).width = 110

        let copyrightTitle = NSTextField(labelWithString: "판권 정보")
        copyrightTitle.font = .systemFont(ofSize: 16, weight: .semibold)
        let copyrightHelp = NSTextField(labelWithString: "입력하면 TXT와 EPUB의 마지막 판권 페이지에 적용됩니다. 비워두면 원고 내용을 사용합니다.")
        copyrightHelp.textColor = .secondaryLabelColor
        copyrightHelp.font = .systemFont(ofSize: 12)
        let copyrightForm = NSGridView(views: [
            [NSTextField(labelWithString: "제목"), titleField],
            [NSTextField(labelWithString: "지은이"), authorField],
            [NSTextField(labelWithString: "발행처"), publisherField],
            [NSTextField(labelWithString: "발행일"), dateField],
            [NSTextField(labelWithString: "UCI"), uciField],
            [NSTextField(labelWithString: "투고메일"), submissionEmailField],
            [NSTextField(labelWithString: "저작권 문구"), rightsField],
        ])
        copyrightForm.rowSpacing = 8
        copyrightForm.columnSpacing = 14
        copyrightForm.column(at: 0).width = 110
        [titleField, authorField, publisherField, dateField, uciField, submissionEmailField, rightsField].forEach {
            $0.placeholderString = "선택 입력"
        }
        saveCopyrightButton.target = self
        saveCopyrightButton.action = #selector(saveCopyrightInfo)
        saveCopyrightButton.bezelStyle = .rounded

        convertButton.target = self
        convertButton.action = #selector(convert)
        convertButton.bezelStyle = .rounded
        convertButton.keyEquivalent = "\r"

        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isDisplayedWhenStopped = false

        statusLabel.textColor = .secondaryLabelColor
        statusLabel.lineBreakMode = .byWordWrapping
        statusLabel.maximumNumberOfLines = 2

        openTXTButton.target = self
        openTXTButton.action = #selector(openTXT)
        openEPUBButton.target = self
        openEPUBButton.action = #selector(openEPUB)
        revealButton.target = self
        revealButton.action = #selector(revealResults)
        setResultButtons(enabled: false)

        let actionRow = NSStackView(views: [convertButton, spinner])
        actionRow.orientation = .horizontal
        actionRow.spacing = 10
        let resultRow = NSStackView(views: [openTXTButton, openEPUBButton, revealButton])
        resultRow.orientation = .horizontal
        resultRow.spacing = 10

        let stack = NSStackView(views: [title, subtitle, form, copyrightTitle, copyrightHelp, copyrightForm, saveCopyrightButton, actionRow, statusLabel, resultRow])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 16
        stack.translatesAutoresizingMaskIntoConstraints = false
        window.contentView?.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: window.contentView!.leadingAnchor, constant: 28),
            stack.trailingAnchor.constraint(equalTo: window.contentView!.trailingAnchor, constant: -28),
            stack.topAnchor.constraint(equalTo: window.contentView!.topAnchor, constant: 28),
            form.widthAnchor.constraint(equalTo: stack.widthAnchor),
            copyrightForm.widthAnchor.constraint(equalTo: stack.widthAnchor),
            statusLabel.widthAnchor.constraint(equalTo: stack.widthAnchor),
        ])
        loadCopyrightInfo()
        inputModeChanged()
        templateChanged()
    }

    private func fileButton(_ title: String, _ action: Selector) -> NSButton {
        let button = NSButton(title: title, target: self, action: action)
        button.bezelStyle = .rounded
        return button
    }

    @objc private func selectHWPX() {
        let panel = NSOpenPanel()
        let isBatch = inputModePopup.indexOfSelectedItem == 1
        panel.allowedFileTypes = isBatch ? nil : ["hwpx"]
        panel.canChooseFiles = !isBatch
        panel.canChooseDirectories = isBatch
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            hwpxURL = url
            hwpxLabel.stringValue = url.path
            if outputURL == nil {
                outputLabel.stringValue = isBatch ? url.path : url.deletingLastPathComponent().path
            }
        }
    }

    @objc private func inputModeChanged() {
        let isBatch = inputModePopup.indexOfSelectedItem == 1
        hwpxURL = nil
        hwpxLabel.stringValue = "선택되지 않음"
        sourceButton.title = isBatch ? "원고 폴더 선택" : "HWPX 선택"
        duplicatePopup.isEnabled = isBatch
        if isBatch {
            templatePopup.selectItem(at: 1)
            templatePopup.isEnabled = false
        } else {
            templatePopup.isEnabled = true
        }
        templateChanged()
    }

    @objc private func selectCover() {
        let panel = NSOpenPanel()
        panel.allowedFileTypes = ["png", "jpg", "jpeg", "webp"]
        panel.allowsMultipleSelection = false
        if panel.runModal() == .OK, let url = panel.url {
            coverURL = url
            coverLabel.stringValue = url.path
        }
    }

    @objc private func selectOutput() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        if panel.runModal() == .OK, let url = panel.url {
            outputURL = url
            outputLabel.stringValue = url.path
        }
    }

    @objc private func templateChanged() {
        let isSerial = templatePopup.indexOfSelectedItem == 1
        statusLabel.stringValue = isSerial
            ? "연재형: 첫 줄은 작품명+화수, 두 번째 비어 있지 않은 줄은 부제목으로 자동 인식합니다."
            : "단행본형: 목차와 여러 장을 자동 인식합니다."
    }

    @objc private func convert() {
        startConversion(overwrite: false)
    }

    private func startConversion(overwrite: Bool) {
        guard let hwpx = hwpxURL, let cover = coverURL else {
            showAlert("HWPX 파일 또는 원고 폴더와 표지 이미지를 모두 선택해 주세요.")
            return
        }
        let isBatch = inputModePopup.indexOfSelectedItem == 1
        let output = outputURL ?? (isBatch ? hwpx : hwpx.deletingLastPathComponent())
        guard let engine = Bundle.main.url(forResource: "epub_engine", withExtension: nil) else {
            showAlert("앱 내부 변환 엔진을 찾지 못했습니다.")
            return
        }

        convertButton.isEnabled = false
        setResultButtons(enabled: false)
        spinner.startAnimation(nil)
        statusLabel.stringValue = isBatch ? "연재 원고를 일괄 변환 중입니다…" : "변환 중입니다…"
        let copyrightArguments = [
            "--title", titleField.stringValue,
            "--author", authorField.stringValue,
            "--publisher", publisherField.stringValue,
            "--date", dateField.stringValue,
            "--uci", uciField.stringValue,
            "--submission-email", submissionEmailField.stringValue,
            "--rights", rightsField.stringValue,
            "--template", templatePopup.indexOfSelectedItem == 1 ? "serial" : "book",
        ] + (overwrite ? ["--overwrite"] : [])
        let sourceArguments = isBatch ? ["--batch-dir", hwpx.path] : ["--hwpx", hwpx.path]
        let batchArguments = isBatch ? [
            "--existing-policy", duplicatePopup.indexOfSelectedItem == 0 ? "overwrite" : "skip"
        ] : []

        DispatchQueue.global(qos: .userInitiated).async {
            let process = Process()
            let outputPipe = Pipe()
            let errorPipe = Pipe()
            process.executableURL = engine
            process.arguments = sourceArguments + [
                "--cover", cover.path,
                "--output-dir", output.path,
            ] + copyrightArguments + batchArguments
            process.standardOutput = outputPipe
            process.standardError = errorPipe
            do {
                try process.run()
                process.waitUntilExit()
                let stdout = String(data: outputPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                let stderr = String(data: errorPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                DispatchQueue.main.async {
                    self.spinner.stopAnimation(nil)
                    self.convertButton.isEnabled = true
                    if process.terminationStatus == 0 {
                        var summary: (Int, Int, Int)?
                        for line in stdout.split(separator: "\n") {
                            if line.hasPrefix("TXT=") {
                                self.txtURL = URL(fileURLWithPath: String(line.dropFirst(4)))
                            } else if line.hasPrefix("EPUB=") {
                                self.epubURL = URL(fileURLWithPath: String(line.dropFirst(5)))
                            } else if line.hasPrefix("SUMMARY=") {
                                let values = line.dropFirst(8).split(separator: "|").compactMap { Int($0) }
                                if values.count == 3 { summary = (values[0], values[1], values[2]) }
                            }
                        }
                        if let result = summary {
                            self.statusLabel.stringValue = "일괄 변환 완료: 성공 \(result.0)개, 건너뜀 \(result.1)개"
                            self.openTXTButton.isEnabled = false
                            self.openEPUBButton.isEnabled = false
                            self.revealButton.isEnabled = true
                        } else {
                            self.statusLabel.stringValue = overwrite
                                ? "완료되었습니다. 기존 TXT와 EPUB을 대치했습니다."
                                : "완료되었습니다. TXT와 EPUB을 저장했습니다."
                            self.setResultButtons(enabled: true)
                        }
                    } else {
                        let message = stderr.isEmpty ? stdout : stderr
                        if message.contains("이미 존재하는 파일:") {
                            let alert = NSAlert()
                            alert.messageText = "같은 이름의 파일이 있습니다"
                            alert.informativeText = message.replacingOccurrences(of: "ERROR=", with: "").trimmingCharacters(in: .whitespacesAndNewlines) + "\n\n기존 TXT와 EPUB을 대치할까요?"
                            alert.alertStyle = .warning
                            alert.addButton(withTitle: "대치")
                            alert.addButton(withTitle: "취소")
                            if alert.runModal() == .alertFirstButtonReturn {
                                self.startConversion(overwrite: true)
                            } else {
                                self.statusLabel.stringValue = "변환을 취소했습니다."
                            }
                        } else {
                            self.showAlert(message)
                            self.statusLabel.stringValue = "변환에 실패했습니다."
                        }
                    }
                }
            } catch {
                DispatchQueue.main.async {
                    self.spinner.stopAnimation(nil)
                    self.convertButton.isEnabled = true
                    self.statusLabel.stringValue = "변환에 실패했습니다."
                    self.showAlert(error.localizedDescription)
                }
            }
        }
    }

    private func setResultButtons(enabled: Bool) {
        openTXTButton.isEnabled = enabled
        openEPUBButton.isEnabled = enabled
        revealButton.isEnabled = enabled
    }

    private var copyrightFields: [(String, NSTextField)] {
        return [
            ("copyright.title", titleField),
            ("copyright.author", authorField),
            ("copyright.publisher", publisherField),
            ("copyright.date", dateField),
            ("copyright.uci", uciField),
            ("copyright.submissionEmail", submissionEmailField),
            ("copyright.rights", rightsField),
        ]
    }

    private func loadCopyrightInfo() {
        let defaults = UserDefaults.standard
        for (key, field) in copyrightFields {
            field.stringValue = defaults.string(forKey: key) ?? ""
        }
    }

    @objc private func saveCopyrightInfo() {
        let defaults = UserDefaults.standard
        for (key, field) in copyrightFields {
            defaults.set(field.stringValue, forKey: key)
        }
        statusLabel.stringValue = "판권정보를 저장했습니다. 다음 실행 때 자동으로 불러옵니다."
    }

    @objc private func openTXT() { if let url = txtURL { NSWorkspace.shared.open(url) } }
    @objc private func openEPUB() { if let url = epubURL { NSWorkspace.shared.open(url) } }
    @objc private func revealResults() {
        if inputModePopup.indexOfSelectedItem == 1, let folder = outputURL ?? hwpxURL {
            NSWorkspace.shared.open(folder)
        } else if let url = epubURL {
            NSWorkspace.shared.activateFileViewerSelecting([url])
        }
    }

    @objc private func showLicenses() {
        guard let url = Bundle.main.url(forResource: "THIRD_PARTY_NOTICES", withExtension: "txt") else {
            showAlert("라이선스 고지 파일을 찾지 못했습니다.")
            return
        }
        NSWorkspace.shared.open(url)
    }

    private func showAlert(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "전자책 변환기"
        alert.informativeText = message.trimmingCharacters(in: .whitespacesAndNewlines)
        alert.alertStyle = .warning
        alert.runModal()
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
