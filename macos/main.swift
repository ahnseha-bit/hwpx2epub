import AppKit
import Darwin
import Foundation

private struct CopyrightPreset: Codable {
    var title: String
    var author: String
    var publisher: String
    var date: String
    var uci: String
    var submissionEmail: String
    var rights: String

    static let empty = CopyrightPreset(title: "", author: "", publisher: "", date: "", uci: "", submissionEmail: "", rights: "")
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private var hwpxURL: URL?
    private var coverURL: URL?
    private var outputURL: URL?
    private var txtURL: URL?
    private var epubURL: URL?
    private var activeProcess: Process?
    private var conversionIsPaused = false
    private var cancellationRequested = false
    private var copyrightPresets: [String: CopyrightPreset] = [:]

    private let hwpxLabel = NSTextField(labelWithString: "선택되지 않음")
    private let coverLabel = NSTextField(labelWithString: "선택되지 않음")
    private let outputLabel = NSTextField(labelWithString: "HWPX 파일과 같은 폴더")
    private let inputModePopup = NSPopUpButton(frame: .zero, pullsDown: false)
    private let templatePopup = NSPopUpButton(frame: .zero, pullsDown: false)
    private let platformPopup = NSPopUpButton(frame: .zero, pullsDown: false)
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
    private let copyrightPresetPopup = NSPopUpButton(frame: .zero, pullsDown: false)
    private let saveCopyrightButton = NSButton(title: "새 프리셋 저장", target: nil, action: nil)
    private let overwriteCopyrightButton = NSButton(title: "현재 프리셋 덮어쓰기", target: nil, action: nil)
    private let deleteCopyrightButton = NSButton(title: "삭제", target: nil, action: nil)
    private let convertButton = NSButton(title: "TXT + EPUB 만들기", target: nil, action: nil)
    private let pauseButton = NSButton(title: "일시중지", target: nil, action: nil)
    private let cancelButton = NSButton(title: "취소", target: nil, action: nil)
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

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let process = activeProcess, process.isRunning else { return .terminateNow }
        let alert = NSAlert()
        alert.messageText = "변환이 진행 중입니다"
        alert.informativeText = "앱을 종료하면 현재 변환이 취소됩니다. 종료할까요?"
        alert.alertStyle = .warning
        alert.addButton(withTitle: "종료하고 취소")
        alert.addButton(withTitle: "계속 변환")
        guard alert.runModal() == .alertFirstButtonReturn else { return .terminateCancel }
        if conversionIsPaused {
            _ = Darwin.kill(-process.processIdentifier, SIGCONT)
        }
        _ = Darwin.kill(-process.processIdentifier, SIGTERM)
        return .terminateNow
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
            contentRect: NSRect(x: 0, y: 0, width: 720, height: 870),
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
        inputModePopup.addItems(withTitles: ["개별 HWPX", "폴더 일괄 처리"])
        inputModePopup.target = self
        inputModePopup.action = #selector(inputModeChanged)
        templatePopup.addItems(withTitles: ["단행본형", "연재형"])
        templatePopup.target = self
        templatePopup.action = #selector(templateChanged)
        platformPopup.addItems(withTitles: ["카카오페이지", "리디북스"])
        platformPopup.target = self
        platformPopup.action = #selector(templateChanged)
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
            [NSTextField(labelWithString: "유통 플랫폼"), platformPopup],
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
        copyrightPresetPopup.target = self
        copyrightPresetPopup.action = #selector(copyrightPresetChanged)
        saveCopyrightButton.target = self
        saveCopyrightButton.action = #selector(saveCopyrightInfo)
        overwriteCopyrightButton.target = self
        overwriteCopyrightButton.action = #selector(overwriteCopyrightPreset)
        deleteCopyrightButton.target = self
        deleteCopyrightButton.action = #selector(deleteCopyrightPreset)
        [saveCopyrightButton, overwriteCopyrightButton, deleteCopyrightButton].forEach { $0.bezelStyle = .rounded }
        let presetRow = NSStackView(views: [copyrightPresetPopup, saveCopyrightButton, overwriteCopyrightButton, deleteCopyrightButton])
        presetRow.orientation = .horizontal
        presetRow.spacing = 8
        let copyrightForm = NSGridView(views: [
            [NSTextField(labelWithString: "제목"), titleField],
            [NSTextField(labelWithString: "지은이"), authorField],
            [NSTextField(labelWithString: "발행처"), publisherField],
            [NSTextField(labelWithString: "발행일"), dateField],
            [NSTextField(labelWithString: "UCI"), uciField],
            [NSTextField(labelWithString: "투고문의"), submissionEmailField],
            [NSTextField(labelWithString: "저작권 문구"), rightsField],
        ])
        copyrightForm.rowSpacing = 8
        copyrightForm.columnSpacing = 14
        copyrightForm.column(at: 0).width = 110
        [titleField, authorField, publisherField, dateField, uciField, submissionEmailField, rightsField].forEach {
            $0.placeholderString = "선택 입력"
        }
        convertButton.target = self
        convertButton.action = #selector(convert)
        convertButton.bezelStyle = .rounded
        convertButton.keyEquivalent = "\r"
        pauseButton.target = self
        pauseButton.action = #selector(togglePauseConversion)
        cancelButton.target = self
        cancelButton.action = #selector(cancelConversion)
        pauseButton.isEnabled = false
        cancelButton.isEnabled = false

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

        let actionRow = NSStackView(views: [convertButton, pauseButton, cancelButton, spinner])
        actionRow.orientation = .horizontal
        actionRow.spacing = 10
        let resultRow = NSStackView(views: [openTXTButton, openEPUBButton, revealButton])
        resultRow.orientation = .horizontal
        resultRow.spacing = 10

        let stack = NSStackView(views: [title, subtitle, form, copyrightTitle, copyrightHelp, presetRow, copyrightForm, actionRow, statusLabel, resultRow])
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
        loadCopyrightPresets()
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
        templatePopup.isEnabled = true
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
        let isRidi = platformPopup.indexOfSelectedItem == 1
        if isSerial && isRidi {
            statusLabel.stringValue = "리디북스 연재형: 2화부터 EPUB 내부 표지와 판권을 모두 제외합니다."
        } else if isSerial {
            statusLabel.stringValue = "카카오페이지 연재형: 표지는 모든 회차에 유지하고, 판권은 1화에만 포함합니다."
        } else {
            statusLabel.stringValue = "단행본형: 표지·목차·본문·판권을 포함합니다."
        }
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
        guard let launcher = Bundle.main.url(forResource: "epub_launcher", withExtension: nil) else {
            showAlert("앱 내부 프로세스 런처를 찾지 못했습니다.")
            return
        }

        convertButton.isEnabled = false
        pauseButton.isEnabled = false
        cancelButton.isEnabled = false
        pauseButton.title = "일시중지"
        conversionIsPaused = false
        cancellationRequested = false
        setResultButtons(enabled: false)
        spinner.startAnimation(nil)
        let templateName = templatePopup.indexOfSelectedItem == 1 ? "연재형" : "단행본형"
        statusLabel.stringValue = isBatch ? "\(templateName) 원고를 일괄 변환 중입니다…" : "변환 중입니다…"
        let copyrightArguments = [
            "--title", titleField.stringValue,
            "--author", authorField.stringValue,
            "--publisher", publisherField.stringValue,
            "--date", dateField.stringValue,
            "--uci", uciField.stringValue,
            "--submission-email", submissionEmailField.stringValue,
            "--rights", rightsField.stringValue,
            "--template", templatePopup.indexOfSelectedItem == 1 ? "serial" : "book",
            "--platform", platformPopup.indexOfSelectedItem == 1 ? "ridi" : "kakao",
        ] + (overwrite ? ["--overwrite"] : [])
        let sourceArguments = isBatch ? ["--batch-dir", hwpx.path] : ["--hwpx", hwpx.path]
        let batchArguments = isBatch ? [
            "--existing-policy", duplicatePopup.indexOfSelectedItem == 0 ? "overwrite" : "skip"
        ] : []

        let process = Process()
        let outputPipe = Pipe()
        process.executableURL = launcher
        process.arguments = [engine.path] + sourceArguments + [
            "--cover", cover.path,
            "--output-dir", output.path,
        ] + copyrightArguments + batchArguments
        process.standardOutput = outputPipe
        process.standardError = outputPipe
        activeProcess = process

        DispatchQueue.global(qos: .userInitiated).async {
            do {
                try process.run()
                DispatchQueue.main.async {
                    if self.activeProcess === process {
                        self.pauseButton.isEnabled = true
                        self.cancelButton.isEnabled = true
                    }
                }
                let combinedOutput = outputPipe.fileHandleForReading.readDataToEndOfFile()
                process.waitUntilExit()
                let stdout = String(data: combinedOutput, encoding: .utf8) ?? ""
                let stderr = ""
                DispatchQueue.main.async {
                    let wasCancelled = self.cancellationRequested
                    self.resetConversionControls()
                    self.spinner.stopAnimation(nil)
                    self.convertButton.isEnabled = true
                    if wasCancelled {
                        self.statusLabel.stringValue = "변환을 취소했습니다. 이미 완료된 결과 파일은 유지됩니다."
                    } else if process.terminationStatus == 0 {
                        var summary: (Int, Int, Int)?
                        var warnings: [String] = []
                        for line in stdout.split(separator: "\n") {
                            if line.hasPrefix("TXT=") {
                                self.txtURL = URL(fileURLWithPath: String(line.dropFirst(4)))
                            } else if line.hasPrefix("EPUB=") {
                                self.epubURL = URL(fileURLWithPath: String(line.dropFirst(5)))
                            } else if line.hasPrefix("SUMMARY=") {
                                let values = line.dropFirst(8).split(separator: "|").compactMap { Int($0) }
                                if values.count == 3 { summary = (values[0], values[1], values[2]) }
                            } else if line.hasPrefix("WARNING=") {
                                warnings.append(String(line.dropFirst(8)))
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
                        if !warnings.isEmpty {
                            self.showAlert("변환은 완료되었지만 확인할 권장 사항이 있습니다.\n\n" + warnings.joined(separator: "\n"))
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
                    self.resetConversionControls()
                    self.spinner.stopAnimation(nil)
                    self.convertButton.isEnabled = true
                    self.statusLabel.stringValue = "변환에 실패했습니다."
                    self.showAlert(error.localizedDescription)
                }
            }
        }
    }

    @objc private func togglePauseConversion() {
        guard let process = activeProcess, process.isRunning else { return }
        let signal = conversionIsPaused ? SIGCONT : SIGSTOP
        guard Darwin.kill(-process.processIdentifier, signal) == 0 else {
            showAlert("변환 프로세스의 상태를 변경하지 못했습니다.")
            return
        }
        conversionIsPaused.toggle()
        pauseButton.title = conversionIsPaused ? "재개" : "일시중지"
        if conversionIsPaused {
            spinner.stopAnimation(nil)
            statusLabel.stringValue = "변환을 일시중지했습니다. 재개를 누르면 현재 지점부터 계속합니다."
        } else {
            spinner.startAnimation(nil)
            statusLabel.stringValue = "변환을 재개했습니다…"
        }
    }

    @objc private func cancelConversion() {
        guard let process = activeProcess, process.isRunning else { return }
        let alert = NSAlert()
        alert.messageText = "변환을 취소할까요?"
        alert.informativeText = "현재 처리 중인 파일은 완성되지 않을 수 있지만, 이미 완료된 일괄 결과는 유지됩니다."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "변환 취소")
        alert.addButton(withTitle: "계속하기")
        guard alert.runModal() == .alertFirstButtonReturn else { return }

        cancellationRequested = true
        pauseButton.isEnabled = false
        cancelButton.isEnabled = false
        statusLabel.stringValue = "변환을 취소하는 중입니다…"
        if conversionIsPaused {
            _ = Darwin.kill(-process.processIdentifier, SIGCONT)
            conversionIsPaused = false
        }
        _ = Darwin.kill(-process.processIdentifier, SIGTERM)
    }

    private func resetConversionControls() {
        activeProcess = nil
        conversionIsPaused = false
        cancellationRequested = false
        pauseButton.title = "일시중지"
        pauseButton.isEnabled = false
        cancelButton.isEnabled = false
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

    private let copyrightPresetStorageKey = "copyright.presets.v2"
    private let selectedCopyrightPresetKey = "copyright.selectedPreset.v2"

    private func currentCopyrightPreset() -> CopyrightPreset {
        CopyrightPreset(
            title: titleField.stringValue,
            author: authorField.stringValue,
            publisher: publisherField.stringValue,
            date: dateField.stringValue,
            uci: uciField.stringValue,
            submissionEmail: submissionEmailField.stringValue,
            rights: rightsField.stringValue
        )
    }

    private func applyCopyrightPreset(_ preset: CopyrightPreset) {
        titleField.stringValue = preset.title
        authorField.stringValue = preset.author
        publisherField.stringValue = preset.publisher
        dateField.stringValue = preset.date
        uciField.stringValue = preset.uci
        submissionEmailField.stringValue = preset.submissionEmail
        rightsField.stringValue = preset.rights
    }

    private func persistCopyrightPresets(selecting name: String) {
        let defaults = UserDefaults.standard
        if let data = try? JSONEncoder().encode(copyrightPresets) {
            defaults.set(data, forKey: copyrightPresetStorageKey)
        }
        defaults.set(name, forKey: selectedCopyrightPresetKey)
        copyrightPresetPopup.removeAllItems()
        copyrightPresetPopup.addItems(withTitles: copyrightPresets.keys.sorted { $0.localizedStandardCompare($1) == .orderedAscending })
        copyrightPresetPopup.selectItem(withTitle: name)
        overwriteCopyrightButton.isEnabled = !copyrightPresets.isEmpty
        deleteCopyrightButton.isEnabled = !copyrightPresets.isEmpty
    }

    private func loadCopyrightPresets() {
        let defaults = UserDefaults.standard
        if let data = defaults.data(forKey: copyrightPresetStorageKey),
           let decoded = try? JSONDecoder().decode([String: CopyrightPreset].self, from: data),
           !decoded.isEmpty {
            copyrightPresets = decoded
        } else {
            var legacy = CopyrightPreset.empty
            for (key, field) in copyrightFields {
                field.stringValue = defaults.string(forKey: key) ?? ""
            }
            legacy = currentCopyrightPreset()
            copyrightPresets = ["기본": legacy]
        }
        let requested = defaults.string(forKey: selectedCopyrightPresetKey) ?? "기본"
        let selected = copyrightPresets[requested] != nil ? requested : copyrightPresets.keys.sorted().first!
        persistCopyrightPresets(selecting: selected)
        applyCopyrightPreset(copyrightPresets[selected] ?? .empty)
    }

    @objc private func copyrightPresetChanged() {
        guard let name = copyrightPresetPopup.selectedItem?.title,
              let preset = copyrightPresets[name] else { return }
        applyCopyrightPreset(preset)
        UserDefaults.standard.set(name, forKey: selectedCopyrightPresetKey)
        statusLabel.stringValue = "‘\(name)’ 판권 프리셋을 불러왔습니다."
    }

    @objc private func saveCopyrightInfo() {
        let alert = NSAlert()
        alert.messageText = "새 판권 프리셋 저장"
        alert.informativeText = "이 판권정보를 구분할 이름을 입력해 주세요."
        alert.addButton(withTitle: "저장")
        alert.addButton(withTitle: "취소")
        let nameField = NSTextField(frame: NSRect(x: 0, y: 0, width: 280, height: 24))
        nameField.placeholderString = "예: 블랙인디고 기본 판권"
        alert.accessoryView = nameField
        guard alert.runModal() == .alertFirstButtonReturn else { return }
        let name = nameField.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty else {
            showAlert("프리셋 이름을 입력해 주세요.")
            return
        }
        if copyrightPresets[name] != nil {
            let confirm = NSAlert()
            confirm.messageText = "같은 이름의 프리셋이 있습니다"
            confirm.informativeText = "‘\(name)’ 프리셋을 현재 입력 내용으로 덮어쓸까요?"
            confirm.addButton(withTitle: "덮어쓰기")
            confirm.addButton(withTitle: "취소")
            guard confirm.runModal() == .alertFirstButtonReturn else { return }
        }
        copyrightPresets[name] = currentCopyrightPreset()
        persistCopyrightPresets(selecting: name)
        statusLabel.stringValue = "‘\(name)’ 판권 프리셋을 저장했습니다."
    }

    @objc private func overwriteCopyrightPreset() {
        guard let name = copyrightPresetPopup.selectedItem?.title else { return }
        copyrightPresets[name] = currentCopyrightPreset()
        persistCopyrightPresets(selecting: name)
        statusLabel.stringValue = "‘\(name)’ 판권 프리셋을 현재 내용으로 덮어썼습니다."
    }

    @objc private func deleteCopyrightPreset() {
        guard let name = copyrightPresetPopup.selectedItem?.title else { return }
        let alert = NSAlert()
        alert.messageText = "판권 프리셋을 삭제할까요?"
        alert.informativeText = "‘\(name)’ 프리셋을 삭제합니다."
        alert.alertStyle = .warning
        alert.addButton(withTitle: "삭제")
        alert.addButton(withTitle: "취소")
        guard alert.runModal() == .alertFirstButtonReturn else { return }

        copyrightPresets.removeValue(forKey: name)
        if copyrightPresets.isEmpty {
            copyrightPresets["기본"] = .empty
        }
        let next = copyrightPresets.keys.sorted { $0.localizedStandardCompare($1) == .orderedAscending }.first!
        persistCopyrightPresets(selecting: next)
        applyCopyrightPreset(copyrightPresets[next] ?? .empty)
        statusLabel.stringValue = "‘\(name)’ 판권 프리셋을 삭제했습니다."
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
