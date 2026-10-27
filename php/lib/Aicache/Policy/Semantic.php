<?php
/**
 * Cache sémantique des pages de recherche (cachebench.policies.semantic) : une recherche
 * assez proche d'une recherche en cache (similarité cosinus >= threshold) reçoit sa page.
 * Les autres pages passent par un LRU exact. Paramètres : threshold, dim.
 *
 * Les vecteurs sont des comptes creux (index => nombre) ; les emplacements sont attribués dans le
 * même ordre qu'en Python pour départager les égalités de la même façon.
 */
class Aicache_Policy_Semantic extends Aicache_Policy_Lru
{
    protected $threshold = 0.85;
    protected $dim = 1024;
    /** emplacement => vecteur creux */
    protected $vec = array();
    protected $norms = array();
    protected $slot = array();
    protected $slotKey = array();
    protected $free;
    protected $intent = array();
    public $approxHits = 0;
    public $falseHits = 0;
    public $measuring = true;
    /** Clé dont la page a servi la dernière requête (une autre recherche après un hit approché). */
    public $served;

    public function __construct($capacity, array $params = array())
    {
        parent::__construct($capacity, $params);
        if (isset($params['threshold'])) {
            $this->threshold = (float) $params['threshold'];
        }
        if (isset($params['dim'])) {
            $this->dim = (int) $params['dim'];
        }
        $this->slotKey = array_fill(0, 64, null);
        $this->free = range(63, 0);
    }

    /** Comptes de trigrammes hachés (index => nombre), comme semantic.counts en Python. */
    public static function counts($text, $dim = 1024, $n = 3)
    {
        $v = array();
        $text = function_exists('mb_strtolower') ? mb_strtolower($text, 'UTF-8') : strtolower($text);
        foreach (preg_split('/\s+/u', trim($text), -1, PREG_SPLIT_NO_EMPTY) as $word) {
            $chars = preg_split('//u', " $word ", -1, PREG_SPLIT_NO_EMPTY);
            for ($i = 0, $m = count($chars) - $n + 1; $i < $m; $i++) {
                $j = crc32(implode('', array_slice($chars, $i, $n))) % $dim;
                $v[$j] = (isset($v[$j]) ? $v[$j] : 0.0) + 1.0;
            }
        }
        return $v;
    }

    public static function norm(array $v)
    {
        $s = 0.0;
        foreach ($v as $x) {
            $s += $x * $x;
        }
        return sqrt($s);
    }

    /** Vecteur normalisé, comme semantic.embed en Python. */
    public static function embed($text, $dim = 1024, $n = 3)
    {
        $v = self::counts($text, $dim, $n);
        $norm = 0.0;
        foreach ($v as $x) {
            $norm += $x * $x;
        }
        if ($norm > 0) {
            $norm = sqrt($norm);
            foreach ($v as $j => $x) {
                $v[$j] = $x / $norm;
            }
        }
        return $v;
    }

    public static function intentOf(Aicache_Request $req)
    {
        foreach ($req->tags as $t) {
            if (strpos($t, 'intent_') === 0) {
                return $t;
            }
        }
        return null;
    }

    public function access(Aicache_Request $req)
    {
        $this->served = $req->key;
        if ($req->text === null || $this->contains($req->key)) {
            return parent::access($req);
        }
        $v = self::counts($req->text, $this->dim);
        $nv = self::norm($v);
        if ($this->slot && $nv > 0) {
            $best = -1;
            $bestSim = 0.0;    // les emplacements vides valent 0, comme les lignes nulles en Python
            foreach ($this->vec as $i => $u) {
                $s = 0.0;
                foreach ($v as $j => $x) {
                    if (isset($u[$j])) {
                        $s += $x * $u[$j];
                    }
                }
                $s = $s / ($this->norms[$i] * $nv);
                if ($s > $bestSim || ($s == $bestSim && $best >= 0 && $i < $best)) {
                    $best = $i;
                    $bestSim = $s;
                }
            }
            if ($best >= 0 && $bestSim >= $this->threshold) {
                $key = $this->slotKey[$best];
                $this->served = $key;
                $this->onHit($key, $req);
                if ($this->measuring) {
                    $this->approxHits++;
                    if ($this->intent[$key] !== self::intentOf($req)) {
                        $this->falseHits++;
                    }
                }
                return true;
            }
        }
        $hit = parent::access($req);
        if ($this->contains($req->key)) {
            $this->store($req->key, $v, self::intentOf($req));
        }
        return $hit;
    }

    protected function store($key, array $v, $intent)
    {
        if (!$this->free) {
            $n = count($this->slotKey);
            for ($i = 0; $i < $n; $i++) {
                $this->slotKey[] = null;
            }
            $this->free = range(2 * $n - 1, $n);
        }
        $i = array_pop($this->free);
        $this->vec[$i] = $v;
        $this->norms[$i] = self::norm($v) ?: 1.0;
        $this->slot[$key] = $i;
        $this->slotKey[$i] = (string) $key;
        $this->intent[$key] = $intent;
    }

    protected function onRemove($key)
    {
        parent::onRemove($key);
        if (isset($this->slot[$key])) {
            $i = $this->slot[$key];
            unset($this->slot[$key], $this->vec[$i], $this->norms[$i], $this->intent[$key]);
            $this->slotKey[$i] = null;
            $this->free[] = $i;
        }
    }
}
