<?php
/**
 * Format de requête commun, identique à cachebench.traces.Request (Python).
 * Compatible PHP 7.0 à 8.x.
 */
class Aicache_Request
{
    const GET = 'get';
    const PURGE = 'purge';

    public $ts;
    public $key;
    public $size;
    public $costMs;
    public $kind;
    public $cacheable;
    /** @var string[] */
    public $tags;
    public $text;
    public $op;

    public function __construct($ts, $key, $size = 1, $costMs = 0.0, $kind = '', $cacheable = true,
                                array $tags = array(), $text = null, $op = self::GET)
    {
        $this->ts = (float) $ts;
        $this->key = (string) $key;
        $this->size = (int) $size;
        $this->costMs = (float) $costMs;
        $this->kind = (string) $kind;
        $this->cacheable = (bool) $cacheable;
        $this->tags = $tags;
        $this->text = ($text === '' ? null : $text);
        $this->op = $op;
    }

    /** Copie avec une taille de 1 (mode « unit » du moteur Python). */
    public function withUnitSize()
    {
        $r = clone $this;
        $r->size = 1;
        return $r;
    }
}
