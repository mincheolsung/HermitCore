/* Copyright (c) 2017, RWTH Aachen University
 * Author(s): Annika Wierichs <annika.wierichs@rwth-aachen.de>
 *
 * Permission to use, copy, modify, and/or distribute this software
 * for any purpose with or without fee is hereby granted, provided
 * that the above copyright notice and this permission notice appear
 * in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL
 * WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED
 * WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
 * AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR
 * CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
 * OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
 * NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN
 * CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

#ifndef UHYVE_IBV_H
#define UHYVE_IBV_H

#include <infiniband/verbs.h>		// Linux include
#include <linux/kvm.h>
#include <stdbool.h>

#define MAX_NUM_OF_IBV_DEVICES 16

extern bool use_ib_mem_pool;

typedef enum {
	UHYVE_PORT_SET_IB_POOL_ADDR        = 0x609,

	UHYVE_PORT_IBV_OPEN_DEVICE         = 0x610,
	UHYVE_PORT_IBV_GET_DEVICE_LIST     = 0x611,
	UHYVE_PORT_IBV_GET_DEVICE_NAME     = 0x612,
	UHYVE_PORT_IBV_QUERY_PORT          = 0x613,
	UHYVE_PORT_IBV_CREATE_COMP_CHANNEL = 0x614,
	UHYVE_PORT_KERNEL_IBV_LOG          = 0x615,

} uhyve_ibv_t;

typedef struct {
	// Parameters:
	int * num_devices;
	// Return value:
	// struct ibv_device * ret[MAX_NUM_OF_IBV_DEVICES];
	struct ibv_device ** ret;
} __attribute__((packed)) uhyve_ibv_get_device_list_t;

typedef struct {
	// Parameters:
	struct ibv_device * device;
	// Return value:
	const char * ret; // TODO Should this be const?
} __attribute__((packed)) uhyve_ibv_get_device_name_t;

typedef struct {
	// Parameters:
	struct ibv_device * device;
	// Return value:
	struct ibv_context * ret;
} __attribute__((packed)) uhyve_ibv_open_device_t;

typedef struct {
	// Parameters:
	struct ibv_context * context;
	uint8_t port_num;
	struct ibv_port_attr * port_attr;
	// Return value:
	int ret;
} __attribute__((packed)) uhyve_ibv_query_port_t;

typedef struct {
	// Parameters:
	struct ibv_context * context;
	// Return value:
	struct ibv_comp_channel * ret;
} __attribute__((packed)) uhyve_ibv_create_comp_channel_t;

void call_ibv_open_device(struct kvm_run * run, uint8_t * guest_mem);
void call_ibv_get_device_name(struct kvm_run * run, uint8_t * guest_mem);
void call_ibv_query_port(struct kvm_run * run, uint8_t * guest_mem);
void call_ibv_create_comp_channel(struct kvm_run * run, uint8_t * guest_mem);
void call_ibv_get_device_list(struct kvm_run * run, uint8_t * guest_mem);

#endif // UHYVE_IBV_H
