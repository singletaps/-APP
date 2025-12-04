package com.example.project1.network

import android.content.Context
import android.content.SharedPreferences

// network/SessionManager.kt

object SessionManager {
    private const val PREFS_NAME = "user_session"
    private const val KEY_ACCESS_TOKEN = "access_token"
    private const val KEY_USER_ID = "user_id"
    private const val KEY_USERNAME = "username"
    
    private var sharedPreferences: SharedPreferences? = null
    
    fun init(context: Context) {
        if (sharedPreferences == null) {
            sharedPreferences = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        }
    }
    
    var accessToken: String?
        get() = sharedPreferences?.getString(KEY_ACCESS_TOKEN, null)
        set(value) {
            sharedPreferences?.edit()?.putString(KEY_ACCESS_TOKEN, value)?.apply()
        }
    
    var userId: Int?
        get() {
            val id = sharedPreferences?.getInt(KEY_USER_ID, -1)
            return if (id != null && id != -1) id else null
        }
        set(value) {
            if (value != null) {
                sharedPreferences?.edit()?.putInt(KEY_USER_ID, value)?.apply()
            } else {
                sharedPreferences?.edit()?.remove(KEY_USER_ID)?.apply()
            }
        }
    
    var username: String?
        get() = sharedPreferences?.getString(KEY_USERNAME, null)
        set(value) {
            if (value != null) {
                sharedPreferences?.edit()?.putString(KEY_USERNAME, value)?.apply()
            } else {
                sharedPreferences?.edit()?.remove(KEY_USERNAME)?.apply()
            }
        }
    
    fun isLoggedIn(): Boolean {
        return !accessToken.isNullOrBlank()
    }
    
    fun logout() {
        sharedPreferences?.edit()?.clear()?.apply()
    }
    
    fun authHeader(): String {
        return "Bearer ${accessToken.orEmpty()}"
    }
}
