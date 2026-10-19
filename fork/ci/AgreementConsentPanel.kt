/*
 * Copyright 2026 Duck Apps Contributor
 * If you have any questions, suggestions, or other inquiries, please email Eltavine <me@eltavine.com>.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package com.eltavine.duckdetector.startup.legal

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsBottomHeight
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.text.input.TextFieldState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.eltavine.duckdetector.R
import com.eltavine.duckdetector.core.designsystem.components.DuckButtonDefaults
import com.eltavine.duckdetector.core.designsystem.theme.DuckTheme
import com.eltavine.duckdetector.core.designsystem.theme.DuckTypography
import com.eltavine.duckdetector.core.ui.components.DetectorHairline
import com.eltavine.duckdetector.core.ui.components.DuckIcon
import io.github.xiaotong6666.uihelper.adaptive.AdaptiveContent
import top.yukonga.miuix.kmp.basic.Button as MiuixButton
import top.yukonga.miuix.kmp.basic.ButtonDefaults as MiuixButtonDefaults
import top.yukonga.miuix.kmp.basic.Text as MiuixText
import top.yukonga.miuix.kmp.theme.MiuixTheme

/**
 * Fork-only replacement for the upstream consent bar.
 *
 * Upstream gates the agree button behind a 30 second wait, a scroll-to-bottom check and an
 * arithmetic answer. This fork only needs the document and one button, so the bar keeps the
 * upstream signature (the screen keeps passing every value) and drops the conditions.
 *
 * The file is copied over the upstream one by `scripts/ci-fork-patches.py` at build time, so
 * the repository itself stays byte-identical to upstream.
 */
@Composable
@Suppress("UNUSED_PARAMETER")
internal fun AgreementConsentPanel(
    countdown: Int,
    timerComplete: Boolean,
    num1: Int,
    num2: Int,
    isAddition: Boolean,
    answerState: TextFieldState,
    mathCorrect: Boolean,
    isScrolledToBottom: Boolean,
    canProceed: Boolean,
    buttonScale: Float,
    onAgree: () -> Unit,
    onContentHeightChanged: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    AdaptiveContent(
        miuix = {
            Column(
                modifier = modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .onSizeChanged { size -> onContentHeightChanged(size.height) }
                        .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal))
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    MiuixButton(
                        onClick = onAgree,
                        modifier = Modifier.widthIn(max = 560.dp).fillMaxWidth(),
                        colors = MiuixButtonDefaults.buttonColorsPrimary(),
                    ) {
                        MiuixText(
                            text = stringResource(R.string.i_agree_continue),
                            style = MiuixTheme.textStyles.button,
                        )
                    }
                    MiuixText(
                        text = stringResource(R.string.agreement_acknowledgement),
                        style = MiuixTheme.textStyles.footnote1,
                        color = MiuixTheme.colorScheme.onSurfaceVariantSummary,
                        modifier = Modifier.widthIn(max = 560.dp),
                    )
                }
                Spacer(modifier = Modifier.windowInsetsBottomHeight(WindowInsets.safeDrawing))
            }
        },
        material = {
            val palette = DuckTheme.palette
            Column(
                modifier = modifier
                    .fillMaxWidth()
                    .background(palette.groupedSurface),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .onSizeChanged { size -> onContentHeightChanged(size.height) },
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    DetectorHairline()
                    Column(
                        modifier = Modifier
                            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal))
                            .widthIn(max = 560.dp)
                            .fillMaxWidth()
                            .padding(start = 20.dp, end = 20.dp, top = 14.dp, bottom = 12.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        Button(
                            onClick = onAgree,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 54.dp),
                            colors = DuckButtonDefaults.filledColors(),
                            contentPadding = DuckButtonDefaults.LargeContentPadding,
                        ) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                DuckIcon(
                                    imageVector = Icons.Rounded.CheckCircle,
                                    contentDescription = null,
                                    modifier = Modifier.size(20.dp),
                                )
                                Text(
                                    text = stringResource(R.string.i_agree_continue),
                                    style = DuckTypography.Headline,
                                    textAlign = TextAlign.Center,
                                )
                            }
                        }
                        Text(
                            text = stringResource(R.string.agreement_acknowledgement),
                            style = DuckTypography.Footnote,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                        )
                    }
                }
                Spacer(modifier = Modifier.windowInsetsBottomHeight(WindowInsets.safeDrawing))
            }
        },
    )
}
