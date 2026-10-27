<?php
/**
 * Inférence du petit réseau exporté par cachebench.ml.MLP (format cachebench-mlp-1).
 * Même calcul que MLP.predict en Python : normalisation, couches denses, ReLU entre elles.
 */
class Aicache_Mlp
{
    const FORMAT = 'cachebench-mlp-1';

    public $meta;
    protected $mean;
    protected $std;
    protected $layers;

    public function __construct(array $model)
    {
        if (!isset($model['format']) || $model['format'] !== self::FORMAT) {
            throw new InvalidArgumentException('modèle au format ' . self::FORMAT . ' attendu');
        }
        $this->meta = $model;
        $this->mean = $model['mean'];
        $this->std = $model['std'];
        $this->layers = $model['layers'];
    }

    public static function load($path)
    {
        $d = json_decode(file_get_contents($path), true);
        if (!is_array($d)) {
            throw new RuntimeException("modèle illisible : $path");
        }
        return new self($d);
    }

    /** Note d'un vecteur de features. */
    public function score(array $x)
    {
        $h = array();
        foreach ($x as $i => $v) {
            $h[] = ($v - $this->mean[$i]) / $this->std[$i];
        }
        $last = count($this->layers) - 1;
        foreach ($this->layers as $l => $layer) {
            $W = $layer['W'];
            $out = $layer['b'];
            $nOut = count($out);
            foreach ($h as $i => $hi) {
                if ($hi == 0.0) {
                    continue;
                }
                $row = $W[$i];
                for ($j = 0; $j < $nOut; $j++) {
                    $out[$j] += $hi * $row[$j];
                }
            }
            if ($l < $last) {
                foreach ($out as $j => $v) {
                    if ($v < 0) {
                        $out[$j] = 0.0;
                    }
                }
            }
            $h = $out;
        }
        return $h[0];
    }
}
