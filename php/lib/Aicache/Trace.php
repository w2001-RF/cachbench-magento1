<?php
/**
 * Lecture et écriture du CSV de trace commun : ts,op,key,size,cost_ms,kind,cacheable,tags,text
 */
class Aicache_Trace
{
    public static $columns = array('ts', 'op', 'key', 'size', 'cost_ms', 'kind', 'cacheable', 'tags', 'text');

    /** Python écrit le CSV sans caractère d'échappement ; PHP < 7.4 n'accepte pas '' ici. */
    private static function esc()
    {
        return PHP_VERSION_ID >= 70400 ? '' : '\\';
    }

    /** @return Aicache_Request[] */
    public static function read($path)
    {
        $f = fopen($path, 'r');
        if (!$f) {
            throw new RuntimeException("trace illisible : $path");
        }
        $header = fgetcsv($f, 0, ',', '"', self::esc());
        $idx = array_flip($header);
        $out = array();
        while (($row = fgetcsv($f, 0, ',', '"', self::esc())) !== false) {
            if ($row === array(null)) {
                continue;
            }
            $tags = isset($idx['tags']) && $row[$idx['tags']] !== '' ? explode('|', $row[$idx['tags']]) : array();
            $out[] = new Aicache_Request(
                $row[$idx['ts']],
                $row[$idx['key']],
                isset($idx['size']) && $row[$idx['size']] !== '' ? (int) $row[$idx['size']] : 1,
                isset($idx['cost_ms']) && $row[$idx['cost_ms']] !== '' ? (float) $row[$idx['cost_ms']] : 0.0,
                isset($idx['kind']) ? $row[$idx['kind']] : '',
                !isset($idx['cacheable']) || !in_array($row[$idx['cacheable']], array('0', 'false', 'False'), true),
                $tags,
                isset($idx['text']) ? $row[$idx['text']] : null,
                isset($idx['op']) && $row[$idx['op']] !== '' ? $row[$idx['op']] : Aicache_Request::GET
            );
        }
        fclose($f);
        return $out;
    }

    /** Ajoute une ligne à un CSV de trace (crée l'en-tête si le fichier est vide). */
    public static function append($path, Aicache_Request $r)
    {
        $f = fopen($path, 'a');
        if (!$f) {
            return false;
        }
        if (flock($f, LOCK_EX)) {
            // taille lue sous verrou : filesize() garde sa valeur en cache pendant toute la requête
            $st = fstat($f);
            if ($st['size'] === 0) {
                fputcsv($f, self::$columns, ',', '"', self::esc());
            }
            fputcsv($f, array(
                sprintf('%.3F', $r->ts), $r->op, $r->key, $r->size, sprintf('%.3F', $r->costMs),
                $r->kind, $r->cacheable ? 1 : 0, implode('|', $r->tags), (string) $r->text,
            ), ',', '"', self::esc());
            flock($f, LOCK_UN);
        }
        fclose($f);
        return true;
    }
}
