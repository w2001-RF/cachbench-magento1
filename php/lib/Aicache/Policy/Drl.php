<?php
/**
 * Éviction apprise (cachebench.policies.drl) : parmi les K pages les moins récemment
 * utilisées, on évince celle que le réseau note le plus haut.
 * Paramètres : model (chemin du JSON entraîné par « cachebench train-drl »), k.
 */
class Aicache_Policy_Drl extends Aicache_Policy_Lru
{
    public static $features = array('log_age_s', 'log_size_kb', 'sqrt_hits', 'log_idle_s', 'log_cost_ms',
        'lru_rank', 'is_product', 'is_category', 'is_search', 'is_home');
    public static $kinds = array('catalog_product_view', 'catalog_category_view',
        'catalogsearch_result_index', 'cms_index_index');

    protected $k = 16;
    /** @var Aicache_Mlp */
    protected $net;
    /** clé => array(insertion_ts, dernier_ts, hits, coût, taille, type) */
    protected $state = array();
    protected $now = 0.0;

    public function __construct($capacity, array $params = array())
    {
        parent::__construct($capacity, $params);
        if (isset($params['k'])) {
            $this->k = (int) $params['k'];
        }
        if (!isset($params['model'])) {
            throw new InvalidArgumentException("drl a besoin d'un modèle entraîné (paramètre model)");
        }
        $this->net = $params['model'] instanceof Aicache_Mlp ? $params['model'] : Aicache_Mlp::load($params['model']);
        if ($this->net->meta['features'] !== self::$features) {
            throw new InvalidArgumentException('modèle entraîné avec d\'autres features');
        }
        if (isset($this->net->meta['k'])) {
            $this->k = (int) $this->net->meta['k'];
        }
    }

    public function access(Aicache_Request $req)
    {
        $this->now = $req->ts;
        return parent::access($req);
    }

    protected function onHit($key, Aicache_Request $req)
    {
        parent::onHit($key, $req);
        $this->state[$key][1] = $req->ts;
        $this->state[$key][2]++;
    }

    protected function onInsert($key, Aicache_Request $req)
    {
        parent::onInsert($key, $req);
        $this->state[$key] = array($req->ts, $req->ts, 0, $req->costMs, $req->size, $req->kind);
    }

    protected function onRemove($key)
    {
        parent::onRemove($key);
        unset($this->state[$key]);
    }

    public function features(array $keys)
    {
        $n = max(1, count($keys) - 1);
        $X = array();
        foreach ($keys as $i => $k) {
            list($ins, $last, $hits, $cost, $size, $kind) = $this->state[$k];
            $x = array(
                log1p(max(0.0, $this->now - $ins)),
                log1p($size / 1024),
                sqrt($hits),
                log1p(max(0.0, $this->now - $last)),
                log1p($cost),
                $i / $n,
            );
            foreach (self::$kinds as $kd) {
                $x[] = $kind === $kd ? 1.0 : 0.0;
            }
            $X[] = $x;
        }
        return $X;
    }

    protected function victim()
    {
        $keys = array();
        foreach ($this->order as $k => $_) {
            $keys[] = (string) $k;
            if (count($keys) >= $this->k) {
                break;
            }
        }
        if (count($keys) === 1) {
            return $keys[0];
        }
        $best = 0;
        $bestScore = -INF;
        foreach ($this->features($keys) as $i => $x) {
            $s = $this->net->score($x);
            if ($s > $bestScore) {   // premier maximum, comme np.argmax
                $best = $i;
                $bestScore = $s;
            }
        }
        return $keys[$best];
    }
}
