/*
 * sensor.c — AGNI RAKSHAK Sensor Node (Cooja / Contiki-NG)
 * ──────────────────────────────────────────────────────────
 * Sends a JSON payload every 5 seconds to the sink node.
 */

#include "contiki.h"
#include "net/ipv6/simple-udp.h"
#include "net/ipv6/uiplib.h"
#include "net/routing/routing.h"
#include "sys/etimer.h"
#include "sys/log.h"
#include "net/linkaddr.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LOG_MODULE "SENSOR"
#define LOG_LEVEL  LOG_LEVEL_INFO

#define UDP_PORT        5678
#define SEND_INTERVAL   (CLOCK_SECOND * 5)

#define TEMP_BASE    20
#define TEMP_RANGE   15
#define HUM_BASE     40
#define HUM_RANGE    40
#define WIND_BASE    5
#define WIND_RANGE   20

static struct simple_udp_connection udp_conn;
static struct etimer timer;

PROCESS(sensor_node_process, "AGNI RAKSHAK Sensor Node");
AUTOSTART_PROCESSES(&sensor_node_process);

PROCESS_THREAD(sensor_node_process, ev, data)
{
  static uip_ipaddr_t dest_ipaddr;

  PROCESS_BEGIN();

  /* Register UDP */
  simple_udp_register(&udp_conn, UDP_PORT, NULL, UDP_PORT, NULL);

  uint8_t node_id = linkaddr_node_addr.u8[LINKADDR_SIZE - 1];
  LOG_INFO("Sensor node %u started\n", node_id);
  
  /* Create an ALL NODES multicast address to guarantee the sink hears it */
  uiplib_ipaddrconv("ff02::1", &dest_ipaddr);

  etimer_set(&timer, SEND_INTERVAL);

  while(1) {
    PROCESS_WAIT_EVENT_UNTIL(etimer_expired(&timer));

    {
      int temp     = TEMP_BASE  + (rand() % TEMP_RANGE);
      int humidity = HUM_BASE   + (rand() % HUM_RANGE);
      int wind     = WIND_BASE  + (rand() % WIND_RANGE);
      int moisture = 40 + (rand() % 30);
      int ph       = 5  + (rand() % 3);
      int light    = 300 + (rand() % 200);
  
      char msg[200];
      snprintf(msg, sizeof(msg),
        "{\"node\":%u,\"temp\":%d,\"humidity\":%d,\"wind\":%d,"
        "\"moisture\":%d,\"ph\":%d,\"light\":%d}",
        node_id, temp, humidity, wind, moisture, ph, light);
  
      LOG_INFO("Sending: %s\n", msg);
      simple_udp_sendto(&udp_conn, msg, strlen(msg), &dest_ipaddr);
    }

    etimer_reset(&timer);
  }

  PROCESS_END();
}
