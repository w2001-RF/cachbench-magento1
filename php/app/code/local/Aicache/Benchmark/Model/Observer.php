<?php
/**
 * Journal des requêtes vitrine au format de trace cachebench (ts,op,key,size,cost_ms,kind,cacheable,tags,text).
 * Le fichier se rejoue ensuite avec « cachebench run » (Python) ou shell/aicache_replay.php,
 * à la place de la trace synthétique.
 */
class Aicache_Benchmark_Model_Observer
{
    /** Routes jamais mises en cache : panier, compte, tunnel de commande. */
    protected static $private = array('checkout', 'customer', 'wishlist', 'sales', 'review', 'newsletter', 'paypal');

    protected function enabled()
    {
        return Mage::getStoreConfigFlag('aicache/trace/enabled');
    }

    protected function file()
    {
        $f = Mage::getStoreConfig('aicache/trace/file');
        if ($f === '' || $f === null) {
            $f = 'var/aicache/trace.csv';
        }
        if (!preg_match('#^([a-zA-Z]:)?[\\\\/]#', $f)) {   // relatif (Windows : C:\... est absolu)
            $f = Mage::getBaseDir() . DS . $f;
        }
        if (!is_dir(dirname($f))) {
            mkdir(dirname($f), 0775, true);
        }
        return $f;
    }

    public function logPage(Varien_Event_Observer $observer)
    {
        try {
            if (!$this->enabled()) {
                return;
            }
            $front = $observer->getEvent()->getFront();
            $request = $front->getRequest();
            $response = $front->getResponse();
            $now = microtime(true);
            $start = isset($_SERVER['REQUEST_TIME_FLOAT']) ? $_SERVER['REQUEST_TIME_FLOAT'] : $now;

            $kind = $request->getRequestedRouteName() . '_' . $request->getRequestedControllerName()
                . '_' . $request->getRequestedActionName();
            $tags = array();
            $text = null;
            if ($p = Mage::registry('current_product')) {
                $tags[] = 'catalog_product_' . $p->getId();
            } elseif ($c = Mage::registry('current_category')) {
                $tags[] = 'catalog_category_' . $c->getId();
            } elseif ($kind === 'catalogsearch_result_index') {
                $tags[] = 'catalogsearch';
                $text = (string) Mage::helper('catalogsearch')->getQueryText();
            } elseif ($kind === 'cms_index_index' || $kind === 'cms_page_view') {
                $page = Mage::getSingleton('cms/page');
                $tags[] = 'cms_page_' . ($page->getIdentifier() ? $page->getIdentifier() : $page->getId());
            }

            $r = new Aicache_Request(
                $now,
                $request->getRequestUri(),
                strlen($response->getBody()),
                ($now - $start) * 1000,
                $kind,
                $this->isCacheable($request, $response),
                $tags,
                $text
            );
            Aicache_Trace::append($this->file(), $r);
        } catch (Exception $e) {
            Mage::logException($e);   // le journal ne doit jamais casser une page
        }
    }

    /** Ce qu'un cache de pages pourrait servir à tout le monde. */
    protected function isCacheable($request, $response)
    {
        if (!$request->isGet() || $response->getHttpResponseCode() != 200) {
            return false;
        }
        if (in_array($request->getRequestedRouteName(), self::$private, true)) {
            return false;
        }
        if (Mage::getSingleton('customer/session')->isLoggedIn()) {
            return false;
        }
        return Mage::helper('checkout/cart')->getSummaryCount() == 0;
    }

    public function logPurge(Varien_Event_Observer $observer)
    {
        try {
            $tags = (array) $observer->getEvent()->getTags();
            if (!$tags || !$this->enabled()) {
                return;
            }
            $tags = array_map('strtolower', $tags);
            $r = new Aicache_Request(microtime(true), '', 0, 0.0, 'purge', true, $tags, null, Aicache_Request::PURGE);
            Aicache_Trace::append($this->file(), $r);
        } catch (Exception $e) {
            Mage::logException($e);
        }
    }
}
