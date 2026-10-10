package com.omnidrama.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.omnidrama.app.ui.theme.*

@Composable
fun BrandLogo(
    modifier: Modifier = Modifier
) {
    val goldMetallic = Brush.linearGradient(
        colors = listOf(
            Color(0xFFFFDF70),
            Color(0xFFFFB800),
            Color(0xFFCC8400)
        )
    )

    val obsidianGlass = Brush.radialGradient(
        colors = listOf(
            Color(0xFF1E2433),
            Color(0xFF0F131D),
            Color(0xFF080B11)
        )
    )

    val rimLightGradient = Brush.sweepGradient(
        colors = listOf(
            Color(0xFFFFDF70),
            Color(0xFF00F2FE),
            Color(0xFFFFB800),
            Color(0xFF7928CA),
            Color(0xFFFFDF70)
        )
    )

    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically
    ) {
        // 曾练AI 电影级黑金透镜徽章
        Box(
            modifier = Modifier
                .size(38.dp)
                .shadow(elevation = 8.dp, shape = CircleShape, spotColor = Color(0xFFFFB800))
                .clip(CircleShape)
                .background(rimLightGradient)
                .padding(1.5.dp) // 极细双色高光外圈
                .clip(CircleShape)
                .background(obsidianGlass),
            contentAlignment = Alignment.Center
        ) {
            // 内层电影光圈环
            Box(
                modifier = Modifier
                    .size(28.dp)
                    .clip(CircleShape)
                    .border(width = 1.dp, color = Color(0xFFFFD700).copy(alpha = 0.5f), shape = CircleShape),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "曾",
                    color = Color(0xFFFFDF70),
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Black,
                    letterSpacing = (-0.5).sp
                )
            }
        }

        Spacer(modifier = Modifier.width(10.dp))

        Column {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = "曾练AI短剧创作",
                    color = Color.White,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.ExtraBold,
                    letterSpacing = 0.3.sp
                )
                Spacer(modifier = Modifier.width(6.dp))
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(
                            Brush.horizontalGradient(
                                listOf(Color(0xFFFFB800), Color(0xFFFF8800))
                            )
                        )
                        .padding(horizontal = 5.dp, vertical = 1.dp)
                ) {
                    Text(
                        text = "PRO",
                        color = Color(0xFF0F131D),
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Black
                    )
                }
            }
            Text(
                text = "好莱坞影视工业级全链路 AI 制片",
                color = Color(0xFF94A3B8),
                fontSize = 10.sp,
                fontWeight = FontWeight.Normal
            )
        }
    }
}
