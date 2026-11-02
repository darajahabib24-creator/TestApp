package com.minicode.nativecode

import android.annotation.SuppressLint
import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.Settings
import android.view.View
import android.view.Gravity
import android.view.ViewGroup
import android.widget.AdapterView
import android.widget.BaseAdapter
import android.widget.Button
import android.widget.EditText
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.LinearLayout
import android.widget.ListView
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import io.github.rosemoe.sora.widget.CodeEditor
import io.github.rosemoe.sora.widget.schemes.EditorColorScheme
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class MainActivity : Activity() {

    private val VS_DARK = 0xFF1E1E1E.toInt()
    private val VS_PANEL = 0xFF252526.toInt()
    private val VS_SIDE = 0xFF333333.toInt()
    private val VS_ACCENT = 0xFF0A7ACC.toInt()
    private val VS_TEXT = 0xFFCCCCCC.toInt()
    private val VS_TABBAR = 0xFF2D2D2D.toInt()
    private val MONO = Typeface.MONOSPACE

    private var workspace: File = File(filesDir, "workspace")
    private var cwd: File = workspace
    private var selectedForAction: File? = null

    private val openTabs = LinkedHashMap<String, CodeEditor>()
    private var currentTab: String? = null

    private lateinit var titleBar: TextView
    private lateinit var tabBar: LinearLayout
    private lateinit var tabScroll: HorizontalScrollView
    private lateinit var editorHost: LinearLayout
    private lateinit var filesPanel: LinearLayout
    private lateinit var terminalPanel: LinearLayout
    private lateinit var deployPanel: LinearLayout
    private lateinit var fileList: ListView
    private lateinit var filesStatus: TextView
    private lateinit var terminalOutput: TextView
    private lateinit var terminalInput: EditText
    private lateinit var deployInfo: TextView
    private lateinit var navButtons: Map<String, Button>

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as MiniCodeApp

        app.checkpoint("onCreate start")

        try {
            app.checkpoint("buildUi: start")
            buildUi()
            app.checkpoint("buildUi: done")
        } catch (e: Exception) {
            val report = "API " + Build.VERSION.SDK_INT + " " +
                Build.MANUFACTURER + " " + Build.MODEL + "\n" +
                android.util.Log.getStackTraceString(e)
            try {
                File(filesDir, "minicode-crash.log").appendText(report + "\n\n")
            } catch (ignored: Exception) {
            }
            try {
                app.saveToDownloads("minicode-crash.txt", report)
            } catch (ignored: Exception) {
            }
            setContentView(textView("Startup error:\n$report\n\nCheckpoints:", 13f, VS_TEXT)
                .apply { setBackgroundColor(VS_DARK)
                    textSize = 12f })
            return
        }

        app.checkpoint("initWorkspace")
        initWorkspace()
        cwd = workspace
        app.checkpoint("refreshFiles")
        refreshFiles()
        status("Workspace: ${workspace.absolutePath}")
        app.checkpoint("all done")
        app.publishLog()
    }

    override fun onBackPressed() {
        if (cwd.parentFile != null && cwd != workspace) {
            cwd = cwd.parentFile!!
            refreshFiles()
            showPanel("files")
        } else {
            super.onBackPressed()
        }
    }

    override fun onPause() {
        openTabs.keys.forEach { saveTab(it) }
        super.onPause()
    }

    // ---------- workspace ----------

    private fun initWorkspace() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R &&
            Environment.isExternalStorageManager()
        ) {
            try {
                val shared = File(Environment.getExternalStorageDirectory(), "minicode")
                shared.mkdirs()
                val probe = File(shared, ".probe")
                probe.writeText("1")
                probe.delete()
                workspace = shared
                return
            } catch (e: Exception) {
                // fall through to internal
            }
        }
        workspace = File(filesDir, "workspace")
        workspace.mkdirs()
    }

    private fun grantButtonPrompt() {
        AlertDialog.Builder(this)
            .setTitle("All files access")
            .setMessage(
                "To open projects from shared storage and keep files after " +
                    "uninstall, grant All files access, then reopen MiniCode."
            )
            .setPositiveButton("Open settings") { _, _ ->
                try {
                    startActivity(
                        Intent(
                            Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                            Uri.parse("package:$packageName")
                        )
                    )
                } catch (e: Exception) {
                    showToast("Settings unavailable on this device")
                }
            }
            .setNegativeButton("Later", null)
            .show()
    }

    // ---------- UI build ----------

    private fun button(label: String, action: () -> Unit): Button =
        Button(this).apply {
            text = label
            textSize = 12f
            isAllCaps = false
            setBackgroundColor(VS_SIDE)
            setTextColor(VS_TEXT)
            setOnClickListener { action() }
        }

    private fun row(vararg actions: Pair<String, () -> Unit>): LinearLayout {
        val row = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            setBackgroundColor(VS_PANEL)
        }
        actions.forEach { (label, action) ->
            row.addView(
                button(label, action),
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            )
        }
        return row
    }

    private fun textView(text: String, size: Float, color: Int): TextView =
        TextView(this).apply {
            this.text = text
            textSize = size
            setTextColor(color)
            setPadding(24, 20, 24, 20)
        }

    private fun addRow(panel: LinearLayout, child: View, fill: Boolean = false) {
        panel.addView(
            child,
            if (fill)
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f
                )
            else
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.WRAP_CONTENT
                )
        )
    }

    @SuppressLint("SetTextI18n")
    private fun buildUi() {
        titleBar = textView("MiniCode", 16f, VS_TEXT).apply {
            typeface = Typeface.DEFAULT_BOLD
            setBackgroundColor(VS_SIDE)
        }

        tabBar = LinearLayout(this).apply { setBackgroundColor(VS_TABBAR) }
        tabScroll = HorizontalScrollView(this).apply {
            isHorizontalScrollBarEnabled = false
            addView(tabBar)
        }

        editorHost = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }

        // Files
        filesStatus = textView("", 12f, VS_TEXT)
        fileList = ListView(this).apply {
            setBackgroundColor(VS_PANEL)
            dividerHeight = 1
        }
        filesPanel = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
        }
        addRow(filesPanel, row(
            "New file" to { newFile() },
            "New folder" to { newFolder() },
            "Delete" to { deleteSelected() },
            "Grant storage" to { grantButtonPrompt() }
        ))
        addRow(filesPanel, filesStatus)
        addRow(filesPanel, fileList, fill = true)

        // Terminal
        terminalOutput = TextView(this).apply {
            textSize = 12f
            typeface = MONO
            setTextColor(VS_TEXT)
            setPadding(24, 24, 24, 24)
            setBackgroundColor(VS_PANEL)
        }
        val termScroll = ScrollView(this).apply { addView(terminalOutput) }
        terminalInput = EditText(this).apply {
            hint = "command (e.g. ls, cat hello.sh, pwd)"
            setSingleLine(true)
            typeface = MONO
            textSize = 13f
        }
        terminalPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        addRow(terminalPanel, termScroll, fill = true)
        addRow(terminalPanel, row(
            "Send" to { sendTerminal() },
            "Run file" to { runCurrentFile() },
            "Clear" to { terminalOutput.text = "" }
        ))
        addRow(terminalPanel, terminalInput)

        // Deploy
        deployInfo = textView(
            "Zip your whole workspace to back it up or move it to a PC.\n" +
                "Workspace: ${workspace.absolutePath}", 13f, VS_TEXT
        )
        deployPanel = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        addRow(deployPanel, row(
            "Zip workspace" to { zipWorkspace() },
            "Share zip" to { shareZip() },
            "Grant storage" to { grantButtonPrompt() }
        ))
        addRow(deployPanel, deployInfo)

        // Panels host
        val panelHost = FrameLayout(this)
        listOf(editorHost, filesPanel, terminalPanel, deployPanel).forEach {
            panelHost.addView(
                it,
                FrameLayout.LayoutParams(
                    FrameLayout.LayoutParams.MATCH_PARENT,
                    FrameLayout.LayoutParams.MATCH_PARENT
                )
            )
        }

        // Bottom nav
        val nav = LinearLayout(this).apply { setBackgroundColor(VS_SIDE) }
        navButtons = linkedMapOf(
            "Editor" to button("Editor") { showPanel("editor") },
            "Files" to button("Files") { showPanel("files") },
            "Terminal" to button("Terminal") { showPanel("terminal") },
            "Deploy" to button("Deploy") { showPanel("deploy") }
        )
        navButtons.forEach { _, b ->
            nav.addView(
                b,
                LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            )
        }

        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        addRow(root, titleBar)
        addRow(root, tabScroll)
        addRow(root, panelHost, fill = true)
        addRow(root, nav)
        val wrapper = FrameLayout(this)
        wrapper.addView(
            root,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        )
        // In-app splash overlay (library-free, no platform risk)
        val splash = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER
            setBackgroundColor(VS_DARK)
            addView(TextView(this@MainActivity).apply {
                text = "MINICODE"
                textSize = 34f
                typeface = Typeface.MONOSPACE
                setTextColor(VS_ACCENT)
                gravity = Gravity.CENTER
            })
            addView(TextView(this@MainActivity).apply {
                text = "code editor • terminal • deploy"
                textSize = 12f
                typeface = Typeface.MONOSPACE
                setTextColor(VS_TEXT)
                gravity = Gravity.CENTER
            })
        }
        wrapper.addView(
            splash,
            FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
            )
        )
        setContentView(wrapper)
        splash.postDelayed({ (wrapper as? ViewGroup)?.removeView(splash) }, 700)
        showPanel("editor")
    }

    // ---------- panels ----------

    private fun showPanel(which: String) {
        val ids = listOf("editor", "files", "terminal", "deploy")
        val panels = mapOf(
            "editor" to editorHost,
            "files" to filesPanel,
            "terminal" to terminalPanel,
            "deploy" to deployPanel
        )
        panels.forEach { (key, panel) ->
            panel.visibility = if (key == which) View.VISIBLE else View.GONE
        }
        navButtons.forEach { (label, b) ->
            b.setTextColor(
                if (label.lowercase() == which) Color.WHITE else VS_TEXT
            )
        }
        if (which == "files") refreshFiles()
    }

    // ---------- files ----------

    private fun refreshFiles() {
        val items = ArrayList<String>()
        val values = ArrayList<File>()
        if (cwd.parentFile != null && cwd.absolutePath != workspace.absolutePath) {
            items.add("../")
            values.add(cwd.parentFile!!)
        }
        try {
            cwd.listFiles()
                ?.sortedWith(
                    compareByDescending<File> { it.isDirectory }.thenBy { it.name }
                )
                ?.forEach { f ->
                    if (f.isDirectory) {
                        items.add("[DIR] ${f.name}/")
                    } else {
                        items.add("${f.name}  (${f.length() / 1024} KB)")
                    }
                    values.add(f)
                }
        } catch (e: Exception) {
            filesStatus.text = "Cannot list $cwd: $e"
        }
        if (items.isEmpty()) {
            items.add("(empty - tap New file to start)")
            values.add(cwd)
        }
        fileList.adapter = object : BaseAdapter() {
            override fun getCount() = items.size
            override fun getItem(position: Int) = values[position]
            override fun getItemId(position: Int) = position.toLong()
            override fun getView(
                position: Int,
                convertView: View?,
                parent: ViewGroup
            ): View = ((convertView as? TextView))?.apply {
                text = items[position]
            } ?: TextView(this@MainActivity).apply {
                text = items[position]
                textSize = 14f
                typeface =
                    if (items[position].startsWith("[DIR]") ||
                        items[position] == "../"
                    ) Typeface.DEFAULT_BOLD else MONO
                setTextColor(VS_TEXT)
                setPadding(36, 30, 24, 30)
                setBackgroundColor(VS_PANEL)
            }
        }
        fileList.onItemClickListener =
            AdapterView.OnItemClickListener { _, _, position, _ ->
                val target = values[position]
                if (target.isDirectory) {
                    cwd = target
                    refreshFiles()
                } else {
                    openTab(target)
                }
            }
        fileList.onItemLongClickListener =
            AdapterView.OnItemLongClickListener { _, _, position, _ ->
                val f = values[position]
                when {
                    f.isFile -> {
                        selectedForAction = f
                        AlertDialog.Builder(this@MainActivity)
                            .setTitle(f.name)
                            .setItems(arrayOf("Delete")) { _, _ -> deleteSelected() }
                            .setNegativeButton("Cancel", null)
                            .show()
                        true
                    }
                    f != cwd -> {
                        selectedForAction = f
                        AlertDialog.Builder(this@MainActivity)
                            .setTitle("Delete folder ${f.name}?")
                            .setPositiveButton("Delete") { _, _ -> deleteSelected() }
                            .setNegativeButton("Cancel", null)
                            .show()
                        true
                    }
                    else -> false
                }
            }
        filesStatus.text = "Path: ${cwd.absolutePath}"
    }

    private fun newFile() {
        val input = EditText(this)
        input.hint = "hello.py"
        AlertDialog.Builder(this)
            .setTitle("New file")
            .setView(input)
            .setPositiveButton("Create") { _, _ ->
                try {
                    val name = input.text.toString().trim()
                    if (name.isNotEmpty()) {
                        val f = File(cwd, name)
                        if (!f.exists()) {
                            f.parentFile?.mkdirs()
                            f.writeText("")
                        }
                        if (f.isFile) openTab(f)
                        showPanel("editor")
                    }
                } catch (e: Exception) {
                    showToast("Create failed: $e")
                }
                refreshFiles()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun newFolder() {
        val input = EditText(this)
        input.hint = "project"
        AlertDialog.Builder(this)
            .setTitle("New folder")
            .setView(input)
            .setPositiveButton("Create") { _, _ ->
                try {
                    val name = input.text.toString().trim()
                    if (name.isNotEmpty()) {
                        File(cwd, name).mkdirs()
                    }
                } catch (e: Exception) {
                    showToast("Create failed: $e")
                }
                refreshFiles()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun deleteSelected() {
        val f = selectedForAction
        if (f == null) {
            showToast("Long-press a file in Files to delete it.")
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Delete ${f.name}?")
            .setMessage(f.absolutePath)
            .setPositiveButton("Delete") { _, _ ->
                if (f.isDirectory) f.deleteRecursively() else f.delete()
                openTabs.remove(f.absolutePath)?.release()
                if (currentTab == f.absolutePath) {
                    currentTab = openTabs.keys.firstOrNull()
                }
                updateTabs()
                showActiveEditor()
                refreshFiles()
                status("Deleted ${f.name}")
            }
            .setNegativeButton("Cancel", null)
            .show()
        selectedForAction = null
    }

    // ---------- editor tabs ----------

    private fun openTab(file: File) {
        val path = file.absolutePath
        if (openTabs[path] == null) {
            if (openTabs.size >= 6) {
                showToast("Close some tabs first (long-press a tab).")
                return
            }
            val editor = CodeEditor(this).apply {
                typefaceText = MONO
                setTextSize(14f)
                setLineSpacing(2f, 1.1f)
                setWordwrap(false)
                setColorScheme(vsCodeScheme())
                runCatching {
                    setEditorLanguage(io.github.rosemoe.sora.langs.java.JavaLanguage())
                }
                setText(runCatching { file.readText() }.getOrDefault(""))
            }
            openTabs[path] = editor
        }
        currentTab = path
        updateTabs()
        showActiveEditor()
    }

    private fun vsCodeScheme(): EditorColorScheme =
        EditorColorScheme().also { scheme ->
            scheme.setColor(EditorColorScheme.WHOLE_BACKGROUND, VS_DARK)
            scheme.setColor(EditorColorScheme.LINE_NUMBER_BACKGROUND, VS_PANEL)
            scheme.setColor(EditorColorScheme.LINE_NUMBER, 0xFF858585.toInt())
            scheme.setColor(EditorColorScheme.LINE_NUMBER_CURRENT, 0xFFF0F0F0.toInt())
            scheme.setColor(EditorColorScheme.SELECTION_INSERT, VS_ACCENT)
            scheme.setColor(EditorColorScheme.TEXT_NORMAL, VS_TEXT)
            scheme.setColor(EditorColorScheme.BLOCK_LINE, 0xFF3C3C3C.toInt())
        }

    private fun showActiveEditor() {
        val path = currentTab
        editorHost.removeAllViews()
        if (path == null) {
            editorHost.addView(textView("Open a file from the Files tab.", 14f, VS_TEXT))
        } else {
            editorHost.addView(openTabs[path] ?: return)
            status(File(path).name)
        }
    }

    private fun updateTabs() {
        tabBar.removeAllViews()
        openTabs.keys.forEach { path ->
            val file = File(path)
            val b = Button(this).apply {
                text = file.name
                textSize = 11f
                isAllCaps = false
                setBackgroundColor(VS_TABBAR)
                setTextColor(VS_TEXT)
                setOnClickListener {
                    currentTab = path
                    showActiveEditor()
                }
                setOnLongClickListener {
                    AlertDialog.Builder(this@MainActivity)
                        .setTitle("Close ${file.name}?")
                        .setMessage("The file is saved automatically.")
                        .setPositiveButton("Close") { _, _ ->
                            saveTab(path)
                            openTabs.remove(path)?.release()
                            currentTab = openTabs.keys.firstOrNull()
                            updateTabs()
                            showActiveEditor()
                        }
                        .setNegativeButton("Cancel", null)
                        .show()
                    true
                }
            }
            tabBar.addView(
                b,
                LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT,
                    ViewGroup.LayoutParams.MATCH_PARENT
                )
            )
        }
        if (openTabs.isEmpty()) {
            val hint = textView("no file open", 12f, VS_TEXT)
            hint.setBackgroundColor(VS_TABBAR)
            tabBar.addView(hint)
        }
    }

    private fun saveTab(path: String) {
        openTabs[path] ?: return
        try {
            File(path).writeText(openTabs[path]!!.text.toString())
            status("Saved ${File(path).name}")
        } catch (e: Exception) {
            showToast("Save failed: $e")
        }
    }

    private fun runCurrentFile() {
        val path = currentTab
        if (path == null) {
            showToast("No file open in the editor.")
            return
        }
        saveTab(path)
        val file = File(path)
        if (file.extension != "sh") {
            showToast(
                "Android apps cannot bundle Python/JS runtimes. Run .sh scripts " +
                    "here, or pair MiniCode with Termux for other runtimes."
            )
            return
        }
        terminalOutput.append("\n--- running ${file.name} ---\n")
        runProcess(listOf("sh", file.absolutePath))
        showPanel("terminal")
    }

    // ---------- terminal ----------

    private fun sendTerminal() {
        val cmd = terminalInput.text.toString().trim()
        if (cmd.isEmpty()) return
        terminalInput.setText("")
        terminalOutput.append("\n$ $cmd\n")
        runProcess(listOf("sh", "-c", cmd))
    }

    private fun runProcess(argv: List<String>) {
        Thread {
            try {
                val pb = ProcessBuilder(argv)
                pb.redirectErrorStream(true)
                pb.directory(cwd)
                val process = pb.start()
                process.inputStream.bufferedReader().forEachLine { line ->
                    runOnUiThread { appendTerm(line) }
                }
                process.waitFor()
                runOnUiThread { appendTerm("") }
            } catch (e: Exception) {
                runOnUiThread { appendTerm("error: $e") }
            }
        }.start()
    }

    private fun appendTerm(line: String) {
        terminalOutput.append(line + "\n")
        (terminalOutput.parent as? ScrollView)?.fullScroll(ScrollView.FOCUS_DOWN)
    }

    // ---------- deploy ----------

    private fun externalGranted(): Boolean =
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.R &&
            Environment.isExternalStorageManager()

    private fun zipWorkspace(): File {
        val outDir = if (externalGranted()) {
            Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
        } else {
            filesDir
        }
        outDir.mkdirs()
        val zip = File(outDir, "minicode_project.zip")
        try {
            ZipOutputStream(FileOutputStream(zip)).use { z ->
                workspace.walkTopDown()
                    .filter { it.isFile && it.extension != "zip" }
                    .forEach { f ->
                        val rel = runCatching { f.relativeTo(workspace).path }
                            .getOrDefault(f.name)
                        z.putNextEntry(ZipEntry(rel))
                        FileInputStream(f).use { it.copyTo(z) }
                        z.closeEntry()
                    }
            }
            deployInfo.append("\nCreated: ${zip.absolutePath}")
            status("ZIP created")
        } catch (e: Exception) {
            showToast("Zip failed: $e")
        }
        return zip
    }

    private fun shareZip() {
        if (!zipWorkspace().exists()) return
        try {
            val send = Intent().apply {
                action = Intent.ACTION_SEND
                type = "text/plain"
                putExtra(
                    Intent.EXTRA_TEXT,
                    "MiniCode project zip: ${zipWorkspace().absolutePath}"
                )
            }
            startActivity(Intent.createChooser(send, "Share"))
        } catch (e: Exception) {
            showToast(e.toString())
        }
    }

    private fun showToast(text: String) =
        Toast.makeText(this, text, Toast.LENGTH_LONG).show()

    private fun status(text: String) {
        titleBar.text = text
    }
}
