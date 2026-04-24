/*
 * sink.c — AGNI RAKSHAK Sink Node (Cooja / Contiki-NG)
 * ─────────────────────────────────────────────────────
 * Receives JSON sensor packets from all sensor nodes via UDP.
 * Prints the raw JSON to stdout (printf) so Cooja's Serial Socket
 * forwards it cleanly to the Python backend over TCP port 5678.
 */

#include "contiki.h"
#include "net/ipv6/simple-udp.h"
#include "net/routing/routing.h"
#include "sys/log.h"
#include <stdio.h>
#include <string.h>

#define LOG_MODULE "SINK"
#define LOG_LEVEL  LOG_LEVEL_INFO

#define UDP_PORT 5678

static struct simple_udp_connection udp_conn;

/* ──────────────────────────────────────────────────────
 * UDP Receiver Callback
 * ────────────────────────────────────────────────────── */
static void
receiver(struct simple_udp_connection *c,
         const uip_ipaddr_t *sender_addr,
         uint16_t sender_port,
         const uip_ipaddr_t *receiver_addr,
         uint16_t receiver_port,
         const uint8_t *data,
         uint16_t datalen)
{
  char msg[200];

  /* Safe copy — null-terminate */
  uint16_t len = datalen < (sizeof(msg) - 1) ? datalen : (sizeof(msg) - 1);
  memset(msg, 0, sizeof(msg));
  memcpy(msg, data, len);

  /* ── LOG for Cooja log panel (human readable) ── */
  LOG_INFO("Received: %s\n", msg);

  /*
   * ── CRITICAL: printf goes to Cooja serial stdout ──
   * This gets forwarded through Cooja's Serial Socket.
   */
  printf("%s\n", msg);
}

/* ──────────────────────────────────────────────────────
 * Main Process
 * ────────────────────────────────────────────────────── */
PROCESS(sink_node_process, "AGNI RAKSHAK Sink Node");
AUTOSTART_PROCESSES(&sink_node_process);

PROCESS_THREAD(sink_node_process, ev, data)
{
  PROCESS_BEGIN();

  /* Initialize DAG root for RPL routing */
  NETSTACK_ROUTING.root_start();

  simple_udp_register(&udp_conn, UDP_PORT,
                      NULL, UDP_PORT, receiver);

  LOG_INFO("Sink Node started as RPL DAG Root.\n");
  printf("SINK_READY\n");   /* Heartbeat for backend */

  PROCESS_END();
}
