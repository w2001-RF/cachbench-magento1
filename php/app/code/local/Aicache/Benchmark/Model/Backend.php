<?php
/**
 * Backend Zend_Cache pour Magento 1 : délègue le stockage à un backend existant
 * (fichier, Redis...) et laisse une politique cachebench décider quoi évincer
 * quand la capacité est atteinte.
 *
 * app/etc/local.xml :
 *   <cache>
 *     <backend>Aicache_Benchmark_Model_Backend</backend>
 *     <backend_options>
 *       <inner_backend>Zend_Cache_Backend_File</inner_backend>   (ou Cm_Cache_Backend_Redis)
 *       <inner_options><cache_dir>var/cache</cache_dir></inner_options>
 *       <policy>cacheus</policy>                 lru, lfu, fifo, drl, semantic, lecar, cacheus, arc, lirs, cacheus_pp, cacheus_pp2
 *       <capacity>67108864</capacity>            octets (nombre d'entrées pour lecar, cacheus, arc et lirs)
 *       <params><model>var/aicache/drl-bytes.json</model></params>
 *       <trace_file>var/aicache/cache-trace.csv</trace_file>   (facultatif)
 *       <state_dir>var/aicache/state</state_dir>    (facultatif, sans APCu : partagé par Apache et la CLI)
 *     </backend_options>
 *   </cache>
 *
 * Fonctionnement : pendant la requête on note les accès (hit sur load, insertion sur save,
 * retrait sur remove/clean) ; à la fin de la requête on les applique, sous verrou, à
 * l'état partagé de la politique, puis on supprime du stockage les clés qu'elle évince.
 * Les pages restent donc servies par le backend d'origine : la politique ne fait que choisir.
 *
 * Limites : les expirations (CLEANING_MODE_OLD) ne sont pas vues par la politique ; une
 * réécriture d'une clé déjà présente compte comme un accès. Le cache sémantique se
 * comporte ici comme un LRU, car un backend Zend ne connaît pas le texte des recherches.
 */
class Aicache_Benchmark_Model_Backend extends Zend_Cache_Backend implements Zend_Cache_Backend_ExtendedInterface
{
    /** @var Zend_Cache_Backend_ExtendedInterface */
    protected $inner;
    protected $ops = array();
    protected $missAt = array();
    protected $registered = false;
    /** @var Aicache_StateStore */
    protected $store;

    protected $_options = array(
        'inner_backend' => 'Zend_Cache_Backend_File',
        'inner_options' => array(),
        'policy' => 'lru',
        'capacity' => 67108864,
        'params' => array(),
        'trace_file' => null,
        'state_name' => 'magento',
        'state_dir' => null,   // sans APCu : dossier du fichier d'état (sinon le dossier temporaire de PHP)
    );

    public function __construct(array $options = array())
    {
        foreach ($options as $k => $v) {
            $this->_options[$k] = $v;   // options propres, en plus de celles de Zend
        }
        $cls = $this->_options['inner_backend'];
        $this->inner = new $cls((array) $this->_options['inner_options']);
        $dir = $this->_options['state_dir'];
        if ($dir && !is_dir($dir)) {
            @mkdir($dir, 0777, true);
        }
        $this->store = new Aicache_StateStore($this->_options['state_name'], $dir ? $dir : null);
    }

    public function setDirectives($directives)
    {
        parent::setDirectives($directives);
        $this->inner->setDirectives($directives);
    }

    protected static function idTag($id)
    {
        return '__id_' . $id;   // tag propre à chaque entrée : sert à retirer une clé précise
    }

    protected function record($op)
    {
        $this->ops[] = $op;
        if (!$this->registered) {
            $this->registered = true;
            register_shutdown_function(array($this, 'flush'));
        }
    }

    public function load($id, $doNotTestCacheValidity = false)
    {
        $data = $this->inner->load($id, $doNotTestCacheValidity);
        if ($data === false) {
            $this->missAt[$id] = microtime(true);
        } else {
            $this->record(array('get', $id, strlen($data), 0.0, array()));
        }
        return $data;
    }

    public function test($id)
    {
        return $this->inner->test($id);
    }

    public function save($data, $id, $tags = array(), $specificLifetime = false)
    {
        $ok = $this->inner->save($data, $id, $tags, $specificLifetime);
        if ($ok) {
            // coût : temps écoulé entre le miss et l'écriture, soit le calcul du bloc ou de la page
            $cost = isset($this->missAt[$id]) ? (microtime(true) - $this->missAt[$id]) * 1000 : 0.0;
            unset($this->missAt[$id]);
            $this->record(array('get', $id, strlen($data), $cost, array_map('strtolower', (array) $tags)));
        }
        return $ok;
    }

    public function remove($id)
    {
        $this->record(array('purge', array(self::idTag($id))));
        return $this->inner->remove($id);
    }

    public function clean($mode = Zend_Cache::CLEANING_MODE_ALL, $tags = array())
    {
        if ($mode === Zend_Cache::CLEANING_MODE_ALL) {
            $this->ops = array(array('reset'));
        } elseif ($mode === Zend_Cache::CLEANING_MODE_MATCHING_TAG || $mode === Zend_Cache::CLEANING_MODE_MATCHING_ANY_TAG
            || $mode === Zend_Cache::CLEANING_MODE_NOT_MATCHING_TAG) {
            if ($mode === Zend_Cache::CLEANING_MODE_MATCHING_TAG) {
                $ids = $this->inner->getIdsMatchingTags($tags);
            } elseif ($mode === Zend_Cache::CLEANING_MODE_MATCHING_ANY_TAG) {
                $ids = $this->inner->getIdsMatchingAnyTags($tags);
            } else {
                $ids = $this->inner->getIdsNotMatchingTags($tags);
            }
            if ($ids) {
                $this->record(array('purge', array_map(array(__CLASS__, 'idTag'), $ids)));
            }
        }
        return $this->inner->clean($mode, $tags);
    }

    /** Applique les accès de la requête à l'état partagé, puis supprime ce que la politique évince. */
    public function flush()
    {
        if (!$this->ops) {
            return;
        }
        $ops = $this->ops;
        $this->ops = array();
        $o = $this->_options;
        $evicted = array();
        $refused = array();
        $trace = $o['trace_file'] ? $o['trace_file'] : null;
        $this->store->update(function ($policy) use ($ops, $o, &$evicted, &$refused, $trace) {
            $unit = in_array($o['policy'], Aicache_Factory::$official, true);
            foreach ($ops as $op) {
                if ($op[0] === 'reset' || $policy === null) {
                    $policy = Aicache_Factory::create($o['policy'], (int) $o['capacity'], (array) $o['params']);
                    if ($op[0] === 'reset') {
                        continue;
                    }
                }
                if ($op[0] === 'purge') {
                    $policy->invalidate($op[1]);
                    $r = new Aicache_Request(microtime(true), '', 0, 0.0, 'purge', true, $op[1], null, Aicache_Request::PURGE);
                } else {
                    list(, $id, $size, $cost, $tags) = $op;
                    $tags[] = Aicache_Benchmark_Model_Backend::idTag($id);
                    $r = new Aicache_Request(microtime(true), $id, $unit ? 1 : $size, $cost, '', true, $tags);
                    $policy->access($r);
                    if (!$policy->contains($id)) {
                        $refused[] = $id;
                    }
                    $r->size = $size;   // le journal garde la vraie taille, même pour une politique qui compte des objets
                }
                if ($trace) {
                    Aicache_Trace::append($trace, $r);
                }
            }
            if ($policy !== null) {
                $evicted = $policy->popEvicted();
            }
            return $policy;
        });
        foreach (array_unique(array_merge($evicted, $refused)) as $id) {
            $this->inner->remove($id);
        }
    }

    // --- le reste est délégué tel quel au backend d'origine ---------------------------------
    public function getIds()
    {
        return $this->inner->getIds();
    }

    public function getTags()
    {
        return $this->inner->getTags();
    }

    public function getIdsMatchingTags($tags = array())
    {
        return $this->inner->getIdsMatchingTags($tags);
    }

    public function getIdsNotMatchingTags($tags = array())
    {
        return $this->inner->getIdsNotMatchingTags($tags);
    }

    public function getIdsMatchingAnyTags($tags = array())
    {
        return $this->inner->getIdsMatchingAnyTags($tags);
    }

    public function getFillingPercentage()
    {
        return $this->inner->getFillingPercentage();
    }

    public function getMetadatas($id)
    {
        return $this->inner->getMetadatas($id);
    }

    public function touch($id, $extraLifetime)
    {
        return $this->inner->touch($id, $extraLifetime);
    }

    public function getCapabilities()
    {
        return $this->inner->getCapabilities();
    }
}
