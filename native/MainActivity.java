package com.revela.app;

import android.os.Bundle;
import androidx.activity.OnBackPressedCallback;
import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(GalleryPlugin.class);
        super.onCreate(savedInstanceState);
        // Botão Voltar: primeiro o app fecha o que estiver aberto (ferramenta, zoom, tela de espera).
        // Sem nada para fechar, o app vai para o segundo plano em vez de fechar e perder a foto.
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (bridge == null || bridge.getWebView() == null) {
                    moveTaskToBack(true);
                    return;
                }
                bridge.getWebView().evaluateJavascript(
                    "(function(){try{return window.revelaBack&&window.revelaBack()?'1':'0'}catch(e){return '0'}})()",
                    value -> {
                        if (value == null || !value.contains("1")) moveTaskToBack(true);
                    }
                );
            }
        });
    }
}
