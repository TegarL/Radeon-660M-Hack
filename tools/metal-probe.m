// SPDX-License-Identifier: GPL-2.0-only
// Public standalone probe adapted from the local experiment on 2026-11-11.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static BOOL fail(NSMutableDictionary *report, NSString *stage, NSString *message) {
    report[@"failed_stage"] = stage;
    report[@"error"] = message ?: @"Metal operation failed";
    return NO;
}

static BOOL complete(id<MTLCommandBuffer> command, NSMutableDictionary *report,
                     NSString *stage) {
    [command commit];
    [command waitUntilCompleted];
    if (command.status != MTLCommandBufferStatusCompleted) {
        return fail(report, stage, command.error.localizedDescription);
    }
    return YES;
}

static BOOL compute(id<MTLDevice> device, id<MTLCommandQueue> queue,
                    id<MTLLibrary> library, NSMutableDictionary *report) {
    NSError *error = nil;
    id<MTLComputePipelineState> pipeline = [device
        newComputePipelineStateWithFunction:[library newFunctionWithName:@"probe_compute"]
        error:&error];
    if (!pipeline) return fail(report, @"compute_pipeline", error.localizedDescription);
    const NSUInteger count = 1024;
    id<MTLBuffer> output = [device newBufferWithLength:count * sizeof(uint32_t)
                                             options:MTLResourceStorageModeShared];
    if (!output) return fail(report, @"compute_buffer", @"Could not allocate shared buffer");
    memset(output.contents, 0, output.length);
    id<MTLCommandBuffer> command = [queue commandBuffer];
    id<MTLComputeCommandEncoder> encoder = [command computeCommandEncoder];
    if (!encoder) return fail(report, @"compute_encoder", @"Could not create compute encoder");
    [encoder setComputePipelineState:pipeline];
    [encoder setBuffer:output offset:0 atIndex:0];
    [encoder dispatchThreadgroups:MTLSizeMake(count / 64, 1, 1)
           threadsPerThreadgroup:MTLSizeMake(64, 1, 1)];
    [encoder endEncoding];
    if (!complete(command, report, @"compute_command")) return NO;
    const uint32_t *values = output.contents;
    for (NSUInteger i = 0; i < count; ++i) {
        if (values[i] != i * 7 + 3) {
            return fail(report, @"compute_readback", [NSString stringWithFormat:
                @"Value %lu was %u, expected %lu", (unsigned long)i,
                values[i], (unsigned long)(i * 7 + 3)]);
        }
    }
    report[@"compute_passed"] = @YES;
    report[@"compute_values_checked"] = @(count);
    return YES;
}

static BOOL render(id<MTLDevice> device, id<MTLCommandQueue> queue,
                   id<MTLLibrary> library, NSMutableDictionary *report) {
    MTLRenderPipelineDescriptor *descriptor = [MTLRenderPipelineDescriptor new];
    descriptor.vertexFunction = [library newFunctionWithName:@"probe_vertex"];
    descriptor.fragmentFunction = [library newFunctionWithName:@"probe_fragment"];
    descriptor.colorAttachments[0].pixelFormat = MTLPixelFormatRGBA8Unorm;
    NSError *error = nil;
    id<MTLRenderPipelineState> pipeline = [device newRenderPipelineStateWithDescriptor:descriptor
                                                                              error:&error];
    if (!pipeline) return fail(report, @"render_pipeline", error.localizedDescription);
    const NSUInteger width = 32, height = 32, rowBytes = 256;
    MTLTextureDescriptor *textureDescriptor = [MTLTextureDescriptor
        texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm
        width:width height:height mipmapped:NO];
    textureDescriptor.storageMode = MTLStorageModePrivate;
    textureDescriptor.usage = MTLTextureUsageRenderTarget;
    id<MTLTexture> texture = [device newTextureWithDescriptor:textureDescriptor];
    id<MTLBuffer> output = [device newBufferWithLength:rowBytes * height
                                             options:MTLResourceStorageModeShared];
    if (!texture || !output) return fail(report, @"render_buffers", @"Could not allocate render resources");
    memset(output.contents, 0, output.length);
    MTLRenderPassDescriptor *pass = [MTLRenderPassDescriptor renderPassDescriptor];
    pass.colorAttachments[0].texture = texture;
    pass.colorAttachments[0].loadAction = MTLLoadActionClear;
    pass.colorAttachments[0].storeAction = MTLStoreActionStore;
    pass.colorAttachments[0].clearColor = MTLClearColorMake(1, 0, 0, 1);
    id<MTLCommandBuffer> command = [queue commandBuffer];
    id<MTLRenderCommandEncoder> encoder = [command renderCommandEncoderWithDescriptor:pass];
    if (!encoder) return fail(report, @"render_encoder", @"Could not create render encoder");
    [encoder setRenderPipelineState:pipeline];
    [encoder setViewport:(MTLViewport){0, 0, width, height, 0, 1}];
    [encoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
    [encoder endEncoding];
    id<MTLBlitCommandEncoder> blit = [command blitCommandEncoder];
    if (!blit) return fail(report, @"render_blit", @"Could not create pixel readback encoder");
    [blit copyFromTexture:texture sourceSlice:0 sourceLevel:0
            sourceOrigin:MTLOriginMake(0, 0, 0) sourceSize:MTLSizeMake(width, height, 1)
                toBuffer:output destinationOffset:0 destinationBytesPerRow:rowBytes
        destinationBytesPerImage:rowBytes * height];
    [blit endEncoding];
    if (!complete(command, report, @"render_command")) return NO;
    const uint8_t expected[4] = {64, 128, 191, 255};
    const uint8_t *pixels = output.contents;
    for (NSUInteger y = 0; y < height; ++y) {
        for (NSUInteger x = 0; x < width; ++x) {
            const uint8_t *pixel = pixels + y * rowBytes + x * 4;
            for (NSUInteger channel = 0; channel < 4; ++channel) {
                if (abs((int)pixel[channel] - expected[channel]) > 1) {
                    return fail(report, @"render_readback", [NSString stringWithFormat:
                        @"Pixel (%lu,%lu), channel %lu was %u, expected %u",
                        (unsigned long)x, (unsigned long)y, (unsigned long)channel,
                        pixel[channel], expected[channel]]);
                }
            }
        }
    }
    report[@"render_passed"] = @YES;
    report[@"render_pixels_checked"] = @(width * height);
    report[@"render_size"] = @[@(width), @(height)];
    return YES;
}

static BOOL probe(NSMutableDictionary *report) {
    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    report[@"metal_available"] = @(device != nil);
    if (!device) return fail(report, @"device", @"No Metal device available");
    report[@"device_name"] = device.name;
    report[@"unified_memory"] = @(device.hasUnifiedMemory);
    id<MTLCommandQueue> queue = [device newCommandQueue];
    if (!queue) return fail(report, @"queue", @"Could not create command queue");
    NSString *source = @"#include <metal_stdlib>\nusing namespace metal;\n"
        "kernel void probe_compute(device uint *out [[buffer(0)]], uint i [[thread_position_in_grid]]) { out[i] = i * 7 + 3; }\n"
        "vertex float4 probe_vertex(uint i [[vertex_id]]) { const float2 p[3] = {float2(-1,-1), float2(3,-1), float2(-1,3)}; return float4(p[i],0,1); }\n"
        "fragment float4 probe_fragment() { return float4(0.25,0.5,0.75,1); }\n";
    NSError *error = nil;
    id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
    if (!library) return fail(report, @"shader_library", error.localizedDescription);
    if (!compute(device, queue, library, report)) return NO;
    return render(device, queue, library, report);
}

static void emit(NSDictionary *report) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:report
        options:NSJSONWritingPrettyPrinted error:NULL];
    fwrite(data.bytes, 1, data.length, stdout);
    fputc('\n', stdout);
}

int main(void) {
    @autoreleasepool {
        NSMutableDictionary *report = [NSMutableDictionary dictionaryWithDictionary:
            @{@"compute_passed": @NO, @"render_passed": @NO}];
#if defined(__x86_64__)
        report[@"architecture"] = @"x86_64";
#else
        report[@"architecture"] = @"arm64";
#endif
        BOOL passed = probe(report);
        report[@"passed"] = @(passed);
        emit(report);
        return passed ? 0 : 2;
    }
}
