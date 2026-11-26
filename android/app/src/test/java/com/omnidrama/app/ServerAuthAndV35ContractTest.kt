package com.omnidrama.app

import com.omnidrama.app.data.local.LocalAndroidEngine
import okhttp3.Request
import org.junit.Assert.*
import org.junit.Test

/**
 * 验证 v3.5.0 云端强鉴权 Header 构造、空令牌隔离与脱敏逻辑.
 */
class ServerAuthAndV35ContractTest {

    @Test
    fun testBuildServerAuthHeaders_WithTokenIncludesBearer() {
        val headers = LocalAndroidEngine.buildServerAuthHeaders("  OD2026-test-token-123  ")
        assertEquals("true", headers["Bypass-Tunnel-Reminder"])
        assertEquals("Bearer OD2026-test-token-123", headers["Authorization"])
    }

    @Test
    fun testBuildServerAuthHeaders_BlankTokenOmitsAuthorization() {
        val headers = LocalAndroidEngine.buildServerAuthHeaders("   ")
        assertEquals("true", headers["Bypass-Tunnel-Reminder"])
        assertFalse(headers.containsKey("Authorization"))
    }

    @Test
    fun testApplyServerAuth_SetsHeaderOnlyWhenNonBlank() {
        val authedReq = LocalAndroidEngine.applyServerAuth(
            Request.Builder().url("https://omnidrama-79709693345.asia-east1.run.app/api/project"),
            "secret-abc"
        ).build()
        assertEquals("Bearer secret-abc", authedReq.header("Authorization"))

        val publicReq = LocalAndroidEngine.applyServerAuth(
            Request.Builder().url("https://omnidrama-79709693345.asia-east1.run.app/api/health"),
            ""
        ).build()
        assertNull(publicReq.header("Authorization"))
    }

    @Test
    fun testMaskKey_ProtectsSecrets() {
        assertEquals("", LocalAndroidEngine.maskKey(""))
        assertEquals("sk-a****9999", LocalAndroidEngine.maskKey("sk-abcdef1234569999"))
    }
}
