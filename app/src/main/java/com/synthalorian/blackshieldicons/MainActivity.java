package com.synthalorian.blackshieldicons;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * Blackshield Icon Pack — minimal dashboard stub.
 * Icon packs are resource bundles; this activity only exists so the app
 * has a launcher entry and can show apply instructions.
 */
public class MainActivity extends Activity {

    private static final int BG = Color.parseColor("#101014");
    private static final int SURFACE = Color.parseColor("#16161C");
    private static final int TEXT = Color.parseColor("#D8D3C8");
    private static final int ACCENT = Color.parseColor("#C1121F");

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setBackgroundColor(BG);
        int pad = (int) (24 * getResources().getDisplayMetrics().density);
        root.setPadding(pad, pad, pad, pad);

        TextView title = new TextView(this);
        title.setText("BLACKSHIELD ICONS");
        title.setTextColor(ACCENT);
        title.setTextSize(28);
        title.setGravity(Gravity.CENTER);
        title.setTypeface(android.graphics.Typeface.DEFAULT_BOLD);
        root.addView(title);

        TextView body = new TextView(this);
        body.setText("Steel + blood icon pack.\n\nApply via your launcher:\n"
                + "Nova → Settings → Look & feel → Icon style\n"
                + "Lawnchair → Settings → General → Icon pack");
        body.setTextColor(TEXT);
        body.setTextSize(16);
        body.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT,
                LinearLayout.LayoutParams.WRAP_CONTENT);
        lp.topMargin = pad;
        lp.bottomMargin = pad;
        body.setLayoutParams(lp);
        root.addView(body);

        TextView credit = new TextView(this);
        credit.setText("Made by synth with synthclaw");
        credit.setTextColor(TEXT);
        credit.setAlpha(0.5f);
        credit.setTextSize(12);
        credit.setGravity(Gravity.CENTER);
        credit.setBackgroundColor(SURFACE);
        credit.setPadding(pad / 2, pad / 4, pad / 2, pad / 4);
        root.addView(credit);

        setContentView(root);
    }
}
