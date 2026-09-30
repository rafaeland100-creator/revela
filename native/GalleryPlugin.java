package com.revela.app;

import android.content.ContentValues;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

// Grava a foto editada na galeria (Imagens/Revela). No Android 10 ou mais novo não precisa de permissão.
@CapacitorPlugin(name = "RevelaGallery")
public class GalleryPlugin extends Plugin {
    @PluginMethod
    public void save(PluginCall call) {
        String data = call.getString("data");
        String name = call.getString("name", "revela-" + System.currentTimeMillis());
        if (data == null) { call.reject("sem dados da imagem"); return; }
        try {
            int comma = data.indexOf(',');
            if (comma >= 0) data = data.substring(comma + 1);
            byte[] bytes = Base64.decode(data, Base64.DEFAULT);
            Uri uri;
            if (Build.VERSION.SDK_INT >= 29) {
                ContentValues v = new ContentValues();
                v.put(MediaStore.Images.Media.DISPLAY_NAME, name + ".jpg");
                v.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                v.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Revela");
                v.put(MediaStore.Images.Media.IS_PENDING, 1);
                uri = getContext().getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
                if (uri == null) { call.reject("o Android não criou o arquivo"); return; }
                try (OutputStream os = getContext().getContentResolver().openOutputStream(uri)) { os.write(bytes); }
                ContentValues done = new ContentValues();
                done.put(MediaStore.Images.Media.IS_PENDING, 0);
                getContext().getContentResolver().update(uri, done, null, null);
            } else {
                File dir = new File(Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_PICTURES), "Revela");
                if (!dir.exists()) dir.mkdirs();
                File f = new File(dir, name + ".jpg");
                try (FileOutputStream os = new FileOutputStream(f)) { os.write(bytes); }
                ContentValues v = new ContentValues();
                v.put(MediaStore.Images.Media.DATA, f.getAbsolutePath());
                v.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
                uri = getContext().getContentResolver().insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, v);
            }
            JSObject r = new JSObject();
            r.put("uri", uri != null ? uri.toString() : "");
            call.resolve(r);
        } catch (Exception e) {
            call.reject(e.getMessage() != null ? e.getMessage() : e.toString());
        }
    }
}
