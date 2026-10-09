package com.omnidrama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Movie
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.omnidrama.app.ui.theme.*

@Composable
fun BrandLogo(
    modifier: Modifier = Modifier
) {
    val goldGradient = Brush.linearGradient(
        colors = listOf(
            Color(0xFFFFDF00),
            Color(0xFFF59E0B),
            Color(0xFFD97706)
        )
    )

    val borderGradient = Brush.linearGradient(
        colors = listOf(
            Color(0xFFFFDF00),
            Color(0xFF7928CA),
            Color(0xFF00F2FE)
        )
    )

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 曾练AI 电影级黄金徽标
        Box(
            modifier = Modifier
                .size(34.dp)
                .shadow(elevation = 6.dp, shape = RoundedCornerShape(10.dp), spotColor = Color(0xFFF59E0B))
                .clip(RoundedCornerShape(10.dp))
                .background(Color(0xFF10131E))
                .border(width = 1.5.dp, brush = borderGradient, shape = RoundedCornerShape(10.dp)),
            contentAlignment = Alignment.Center
        ) {
            Box(
                modifier = Modifier
                    .size(24.dp)
                    .clip(RoundedCornerShape(6.dp))
                    .background(goldGradient),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "曾",
                    color = Color(0xFF0D1117),
                    fontSize = 15.sp,
                    fontWeight = FontWeight.ExtraBold,
                    fontFamily = FontFamily.Serif
                )
            }
        }

        Spacer(modifier = Modifier.width(10.dp))

        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "曾练AI短剧创作",
                    color = Color(0xFFF8FAFC),
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = 0.5.sp
                )
                Spacer(modifier = Modifier.width(6.dp))
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(Color(0xFFF59E0B).copy(alpha = 0.2f))
                        .border(0.5.dp, Color(0xFFF59E0B), RoundedCornerShape(4.dp))
                        .padding(horizontal = 4.dp, vertical = 1.dp)
                ) {
                    Text(
                        text = "PRO",
                        color = Color(0xFFFFD700),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.ExtraBold
                    )
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "Hollywood SOTA · 影视工业级全链路",
                    color = Color(0xFF94A3B8),
                    fontSize = 9.5.sp
                )
            }
        }
    }
}
