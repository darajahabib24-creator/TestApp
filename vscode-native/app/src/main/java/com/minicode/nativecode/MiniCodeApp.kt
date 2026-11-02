package com.minicode.nativecode

import android.app.Application
import android.content.ContentValues
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date

/** Crash + checkpoint logger. Set up before any Activity can fail. */
class MiniCodeApp : Application() {

    companion object {
        lateinit var instance: MiniCodeApp
            private set
    }

    private lateinit var logFile: File

    override fun onCreate() {
        super.onCreate()
        instance = this
        logFile = File(filesDir, "minicode-checkpoints.log")
        Thread.setDefaultUncaughtExceptionHandler { thread, error ->
            try {
                val stamp = SimpleDateFormat("MM-dd HH:mm:ss").format(Date())
                val report =
                    "[$stamp] CRASH in thread ${thread.name}\n" +
                        android.util.Log.getStackTraceString(error) +
                        "\nCHECKPOINTS:\n" +
                        (if (logFile.exists()) logFile.readText() else "(none)")
                saveToDownloads("minicode-crash.txt", report)
                logFile.appendText("\n$report")
            } catch (ignored: Exception) {
            }
        }
    }

    fun checkpoint(name: String) {
        try {
            logFile.appendText("[${stamp()}] $name\n")
        } catch (ignored: Exception) {
        }
    }

    private fun stamp(): String =
        SimpleDateFormat("HH:mm:ss").format(Date())

    fun saveToDownloads(name: String, text: String) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            return
        }
        try {
            val values = ContentValues()
            values.put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            values.put(MediaStore.MediaColumns.MIME_TYPE, "text/plain")
            values.put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            val collection = MediaStore.Downloads.getContentUri("external")
            val uri = contentResolver.insert(collection, values) ?: return
            contentResolver.openOutputStream(uri)?.use { os ->
                os.write(text.toByteArray())
                os.flush()
            }
        } catch (ignored: Exception) {
        }
    }

    /** Copies the checkpoint log to Downloads so the user can share it. */
    fun publishLog() {
        try {
            if (logFile.exists()) {
                saveToDownloads(
                    "minicode-checkpoints.txt",
                    logFile.readText()
                )
            }
        } catch (ignored: Exception) {
        }
    }
}
